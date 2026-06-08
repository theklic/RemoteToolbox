<h1 align="center">🧰 RemoteToolbox</h1>

<p align="center">
  <em>Chat with your own tools, running on your own hardware, from anywhere.</em>
</p>

<p align="center">
  A self-hostable framework that bridges a chat app (Telegram, console, …) →
  a <strong>local LLM</strong> on your home server → <strong>tools you build yourself</strong>.
</p>

---

## What is this?

RemoteToolbox lets you talk to a small AI agent over a chat app, where that
agent runs **on your own machine** and can call **tools you wrote yourself**.

Think of it as a tiny, personal, self-hosted version of a tool-using assistant:

```
  ┌────────────┐      ┌──────────────────────────────────────────┐
  │  Telegram  │      │              your home server            │
  │  (or any   │◄────►│                                          │
  │   chat)    │      │   RemoteToolbox                          │
  └────────────┘      │   ├─ chat adapter   (Telegram/console)   │
       remote         │   ├─ orchestrator   (the agent loop)     │
       access         │   ├─ local LLM      (Ollama)             │
                      │   └─ YOUR TOOLS     (./tools, gitignored)│
                      └──────────────────────────────────────────┘
```

You bring the tools. RemoteToolbox handles the chat plumbing, the LLM
orchestration, the tool-calling loop, and the security boundaries — so adding a
new capability is "drop a Python file in `tools/` and restart."

### Why it exists

- **Privacy first.** The model and your tools run locally. Nothing leaves your
  network except the chat messages you choose to send.
- **Your tools, your rules.** Tools are just small Python functions. Write them
  by hand or vibe-code them with [Claude Code](https://claude.com/code).
- **Nothing private in git.** This repo is **framework + docs only**. Your
  actual tools and *all* credentials live in gitignored folders and never get
  committed. See [`SECURITY.md`](docs/SECURITY.md).
- **Small on purpose.** This is not a sprawling agent platform. It's for a
  handful of personal tools you actually use. Like a much smaller, friendlier
  cousin of the big agent frameworks.

---

## Quickstart

> Full setup (home server, remote access, hardening) is in
> [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md). This is the 5-minute local version.

**1. Install [Ollama](https://ollama.com) and pull a tool-capable model:**

```bash
ollama pull llama3.1        # any model that supports tool calling
```

**2. Clone and install RemoteToolbox:**

```bash
git clone https://github.com/theklic/RemoteToolbox.git
cd RemoteToolbox
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

**3. Add your first tool** (copy an example into the gitignored `tools/` dir):

```bash
cp -r examples/tools/hello tools/hello
```

**4. Configure and run — start with the console adapter (no Telegram needed):**

```bash
cp .env.example .env
cp config.example.yaml config.yaml
python -m remotetoolbox            # uses chat.adapter: console by default
```

Now chat in your terminal:

```
you ›  say hello to Sam
bot ›  Hello, Sam! 👋
```

**5. Go remote with Telegram** — create a bot via [@BotFather](https://t.me/BotFather),
put the token in `.env`, set `chat.adapter: telegram` in `config.yaml`, and rerun.
See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

---

## Writing a tool (the whole point)

A tool is a plain Python function with a decorator. Drop it anywhere under
`tools/` and RemoteToolbox auto-discovers it on startup.

```python
# tools/weather/tool.py
from remotetoolbox import tool

@tool(description="Get the current weather for a city.")
def get_weather(city: str) -> str:
    # ... call your weather API, read a sensor, whatever ...
    return f"It's 21°C and sunny in {city}."
```

That's it. Restart and ask the bot "what's the weather in Oslo?" — the LLM will
call `get_weather("Oslo")` and reply with the result.

The decorator turns your type hints + docstring into the JSON schema the LLM
needs. Full guide, including secrets, async tools, and connecting existing MCP
servers: **[`docs/WRITING_TOOLS.md`](docs/WRITING_TOOLS.md)**.

---

## Vibe-coding with Claude Code

This repo is built to be extended by AI coding assistants. [`CLAUDE.md`](CLAUDE.md)
gives Claude Code (or any agent) the project conventions so you can say:

> "Add a tool that turns my living-room lights off via the Hue API."

…and get a correct, idiomatic tool in `tools/`. The framework's contracts are
small and documented precisely so an agent can plug in without reading the whole
codebase.

---

## Documentation

| Doc | What's in it |
|-----|--------------|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | How the pieces fit; the agent loop; extension points. |
| [`docs/WRITING_TOOLS.md`](docs/WRITING_TOOLS.md) | The tool authoring guide (start here to build things). |
| [`docs/CHAT_ADAPTERS.md`](docs/CHAT_ADAPTERS.md) | Add a new chat frontend (Discord, Matrix, …). |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Home-server setup, remote access, running as a service. |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Credentials, the gitignore promise, exposure & access control. |
| [`CLAUDE.md`](CLAUDE.md) | Conventions for extending the project with an AI assistant. |

---

## Project status

Early framework scaffold. The contracts (tool decorator, LLM backend interface,
chat adapter interface) are the stable surface; everything else is meant to be
forked and tinkered with. Contributions to the **framework and docs** are
welcome — but remember tools themselves are never committed here.

## License

[MIT](LICENSE).
