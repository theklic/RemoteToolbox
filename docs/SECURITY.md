# Security

RemoteToolbox runs code on your home server, holds your credentials, and is
reachable from a chat app. Treat it accordingly. This document covers the
project's privacy promise, secret handling, and the realistic threat model.

## The core promise: nothing private in git

This repository is **framework + documentation only**. Two things never get
committed:

1. **Your tools** — everything under `./tools` (the framework auto-discovers
   them there).
2. **All credentials** — `.env`, keys, tokens, `config.yaml`.

This is enforced by [`.gitignore`](../.gitignore). Before pushing, verify:

```bash
git status --ignored        # your tools/ and .env should appear under "Ignored"
# Prints private tools/secrets if any were committed; otherwise prints "clean".
# (The committed examples/, tools/README.md and tools/.gitkeep are expected.)
git ls-files | grep -E '^tools/|^\.env$|^config\.yaml$' \
  | grep -vE '^tools/(README\.md|\.gitkeep)$' || echo clean
```

If you add new secret locations, **add them to `.gitignore` first**.

## Where secrets live

| Kind | Goes in | Committed? |
|---|---|---|
| Telegram bot token | `.env` (`TELEGRAM_BOT_TOKEN`) | ❌ |
| Tool API keys/tokens | `.env` (read via `os.environ`) | ❌ |
| Non-secret runtime settings | `config.yaml` | ❌ (use `config.example.yaml` as the committed template) |
| Example/placeholder values | `*.example` files | ✅ |

`config.yaml` references secrets as `${VAR}` and the loader fills them from the
environment, so tokens never have to be written into a file that might get
shared.

## Access control (who can talk to the bot)

A Telegram bot token is effectively public the moment anyone messages your bot —
**anyone who finds it can send messages.** RemoteToolbox therefore enforces an
**allowlist**:

- `RTB_ALLOWED_USERS` is a comma-separated list of Telegram user IDs.
- **Empty allowlist = nobody is allowed.** This is the safe default; a freshly
  started bot rejects everyone until you add yourself.
- Find your ID by messaging [@userinfobot](https://t.me/userinfobot).

```
RTB_ALLOWED_USERS=123456789
```

Every incoming message is checked against this list before it reaches the agent.

## Threat model — be realistic

The agent can call your tools, and your tools can do real things (read files,
hit APIs, toggle hardware). The LLM decides *which* tools to call based on chat
input. So:

- **Tools are a capability grant.** Only add tools you'd be comfortable letting
  an imperfect assistant invoke. Don't write a `run_shell(command)` tool unless
  you fully accept the consequences.
- **Any file in a tools directory runs at startup.** Discovery *imports* every
  `*.py` under `tools.paths` (top-level code runs then), so dropping a file in
  `tools/` is equivalent to running it. Only put code you trust there.
- **Scope tools narrowly.** Prefer `lights_off()` over `system_exec(cmd)`. Prefer
  read-only over write where you can.
- **Validate inputs** in tools that touch the filesystem or network. The `city`
  argument came from an LLM that was steered by chat text — treat it as untrusted.
- **Don't pass secrets as tool *arguments*.** Tools should read secrets from
  `os.environ`, not take them as parameters. Argument **names** are logged at
  `INFO` and full argument **values** at `DEBUG`, so a token passed as an argument
  could land in your logs. Keep secrets in `.env`.
- **Prompt injection is possible.** If a tool returns attacker-controlled text
  (e.g. the contents of a web page or an email), the model may be influenced by
  it. Keep high-impact tools out of reach of such flows, or require explicit
  confirmation patterns you build into the tool.
- **The model runs locally**, so your prompts and tool data don't leave your
  network — but the **chat transport does** (Telegram's servers see message
  text). Don't send anything to the bot you wouldn't put in a Telegram chat.

### External MCP servers are arbitrary commands

Configuring `tools.mcp_servers` (see [WRITING_TOOLS.md](WRITING_TOOLS.md)) tells
RemoteToolbox to **launch a local command** (e.g. `npx -y @scope/server-…`) and
trust the tools it advertises. That means:

- You're running third-party code with your user's privileges, and (for `npx`)
  pulling it from a package registry at run time. **Pin versions** and prefer
  servers you've vetted.
- A filesystem/exec MCP server is as powerful as what you scope it to — give it
  the narrowest path/permissions that work (e.g. a single shared directory).
- Its tool results flow back into the model, so the prompt-injection note above
  applies to them too.

## Network exposure

The recommended Telegram setup uses **long-polling** (the bot reaches out to
Telegram), so you do **not** need to open any inbound ports or expose your
server to the internet. Prefer this over webhooks for a home server. Keep Ollama
bound to localhost (or your LAN) — don't expose `:11434` publicly.

See [DEPLOYMENT.md](DEPLOYMENT.md) for hardening the running service.

## If a secret leaks

1. Rotate it immediately (revoke the Telegram token via @BotFather; rotate API
   keys at the provider).
2. If it was committed, rotating is **mandatory** — rewriting git history does
   not guarantee the secret wasn't already cloned/cached.
3. Add the leaked path to `.gitignore` so it can't happen again.

## Quick audit before you push

```bash
git ls-files | grep -Ev '^(examples/|docs/|src/|tests/)|\.example$' | grep -iE 'token|secret|key|(^|/)\.env$|config\.yaml' || echo "clean"
```

Output should be `clean`.
