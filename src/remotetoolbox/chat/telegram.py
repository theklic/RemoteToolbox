"""Telegram adapter — the primary way to use RemoteToolbox remotely.

Requires the ``telegram`` extra::

    pip install -e ".[telegram]"

ACCESS CONTROL: only user IDs in ``chat.telegram.allowed_users`` (from
``RTB_ALLOWED_USERS``) may interact. An empty allowlist means *nobody* — a safe
default so a freshly-started bot isn't open to the world. See docs/SECURITY.md.
"""

from __future__ import annotations

import asyncio
import logging

from .. import messaging
from ..config import TelegramConfig
from .base import Assemble, ChatAdapter

log = logging.getLogger(__name__)

# Telegram rejects messages longer than this many characters.
_TELEGRAM_LIMIT = 4096


def _chunks(text: str, limit: int = _TELEGRAM_LIMIT) -> list[str]:
    """Split ``text`` into Telegram-sized pieces, preferring newline boundaries.

    Empty text yields no chunks (Telegram rejects empty messages). When a split
    falls on a newline that newline is consumed; hard splits keep every character.
    """
    if not text:
        return []
    parts: list[str] = []
    rest = text
    while len(rest) > limit:
        cut = rest.rfind("\n", 0, limit)
        if cut <= 0:  # no newline in range — hard split
            parts.append(rest[:limit])
            rest = rest[limit:]
        else:
            parts.append(rest[:cut])
            rest = rest[cut + 1:]  # drop the newline we split on
    if rest:
        parts.append(rest)
    return parts


class TelegramAdapter(ChatAdapter):
    def __init__(self, config: TelegramConfig, assemble: Assemble) -> None:
        super().__init__(assemble)
        self.config = config
        if not config.token:
            raise RuntimeError(
                "Telegram adapter selected but TELEGRAM_BOT_TOKEN is empty. "
                "Create a bot via @BotFather and set it in .env."
            )
        # Ordered list (config order) for the default recipient; set for membership.
        self.allowed_ordered = config.allowed_user_ids_ordered
        self.allowed = set(self.allowed_ordered)
        if not self.allowed:
            log.warning(
                "RTB_ALLOWED_USERS is empty: the bot will refuse EVERYONE. "
                "Add your Telegram user ID to talk to it."
            )

    def serve(self) -> None:
        from telegram import Update
        from telegram.ext import (
            ApplicationBuilder,
            CommandHandler,
            ContextTypes,
            MessageHandler,
            filters,
        )

        def _authorized(update: Update) -> bool:
            user = update.effective_user
            return bool(user and user.id in self.allowed)

        async def _post_init(app: object) -> None:
            # Build tools + LLM inside PTB's own event loop.
            self.orchestrator = await self._assemble()

            # Wire outbound messaging so tools can notify() proactively. Sends go
            # through the running bot; default target is the first allowed user.
            async def _send(text: str, to: str) -> None:
                for part in _chunks(text):
                    await app.bot.send_message(chat_id=int(to), text=part)  # type: ignore[attr-defined]

            messaging.configure(
                send=_send,
                loop=asyncio.get_running_loop(),
                default_to=self.allowed_ordered[0] if self.allowed_ordered else None,
                orchestrator=self.orchestrator,
            )

        async def _post_shutdown(_app: object) -> None:
            messaging.reset()
            if self.orchestrator is not None:
                await self.orchestrator.aclose()

        async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
            if not _authorized(update):
                log.warning("Rejected message from unauthorized user %s", update.effective_user)
                await update.message.reply_text("⛔ Not authorized.")
                return
            assert self.orchestrator is not None
            chat_id = str(update.effective_chat.id)
            await ctx.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            reply = await self.orchestrator.handle(chat_id, update.message.text or "")
            for part in _chunks(reply):
                await update.message.reply_text(part)

        async def on_reset(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
            if not _authorized(update) or self.orchestrator is None:
                return
            self.orchestrator.reset(str(update.effective_chat.id))
            await update.message.reply_text("Conversation cleared.")

        app = (
            ApplicationBuilder()
            .token(self.config.token)
            .post_init(_post_init)
            .post_shutdown(_post_shutdown)
            .build()
        )
        app.add_handler(CommandHandler("reset", on_reset))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

        log.info("Telegram bot starting (polling). Authorized users: %s", self.allowed or "NONE")
        app.run_polling()  # blocks; owns its own event loop
