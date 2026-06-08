<h1 align="center">🧰 RemoteToolbox</h1>

<p align="center">
  <em>Chat with your own tools, running on your own computer, from anywhere.</em>
</p>

<p align="center">
  Text a chat bot → it talks to a private AI on your home computer →
  that AI runs <strong>little tools you made yourself</strong>.
</p>

---

## What is this? (in plain English)

Imagine texting a personal assistant that lives on *your* computer at home. You
can ask it things like *"is the garage door open?"* or *"add milk to my shopping
list"* — and it actually does them, because **you** gave it small tools for those
jobs.

RemoteToolbox is the plumbing that makes that possible. It connects three things:

```
   📱 a chat app            🧠 a private AI               🔧 your tools
   (Telegram, or your   →   (runs on your computer,   →   (small bits of code
    terminal)               not in the cloud)             you wrote, e.g.
                                                          "check the weather")
```

You only have to write the **tools**. RemoteToolbox handles the chat, the AI, and
wiring them together. Adding a new ability is basically: *drop a small file in a
folder and restart.*

> **New to these words?** AI, "model", "tool", "local", "MCP"… see the plain-language
> [**Glossary**](docs/GLOSSARY.md). You don't need to understand all of it to start.

### Why people use it

- 🔒 **Private.** The AI runs on your machine. Your tools and data don't go to a
  company's cloud — only the chat messages you choose to send.
- 🧰 **Yours.** Tools are tiny pieces of code. Write them yourself, or have an AI
  assistant like [Claude Code](https://claude.com/code) write them *for* you.
- 🙈 **Nothing private gets shared.** This project is just the *framework* — your
  actual tools and passwords stay on your computer and are never uploaded. See
  [Security](docs/SECURITY.md).
- 🐣 **Small on purpose.** This is for a handful of personal tools you'll really
  use — not a giant platform. Easy to understand, easy to tinker with.

---

## Is this for you?

This is a good fit if:

- ✅ You have **a computer that's usually on** (a spare laptop, a Raspberry Pi, a
  home server, a desktop) to run things on.
- ✅ You're OK **running a few commands in a terminal** — or you're happy to let an
  AI assistant walk you through it.
- ✅ You want a private assistant for **small, personal jobs**.

You do **not** need to be an experienced programmer. If you can copy-paste
commands and follow steps, you can run this. If you get stuck, the
[Troubleshooting](docs/DEPLOYMENT.md#troubleshooting) section and an AI assistant
can usually get you unstuck.

---

## What you'll need

Three things. Don't worry — each links to a friendly install page.

| Thing | What it is | Get it |
|---|---|---|
| **Python 3.10+** | The programming language this is written in. You install it once. | [python.org/downloads](https://www.python.org/downloads/) |
| **Ollama** | A free app that runs an AI model *on your own computer* (no internet, no account). | [ollama.com](https://ollama.com) |
| **A Telegram account** *(optional)* | Only if you want to chat from your phone. You can skip this at first and chat from your computer's terminal instead. | [telegram.org](https://telegram.org) |

> 💡 **Not sure you can do this yourself?** Open this project in
> [Claude Code](https://claude.com/code) and say *"help me set up RemoteToolbox."*
> It can read [CLAUDE.md](CLAUDE.md) and do most of the work with you.

---

## Quickstart (about 10 minutes)

We'll start the **simplest way**: chatting in your own terminal, no phone or
accounts needed. You can add Telegram afterwards.

### Step 1 — Get an AI model running

After installing [Ollama](https://ollama.com), open a terminal and run:

```bash
ollama pull llama3.1
```

This downloads a free AI model to your computer. (`llama3.1` is a solid starter
model that knows how to use tools. Others work too — see the
[Glossary](docs/GLOSSARY.md#model).)

### Step 2 — Download RemoteToolbox and set it up

```bash
git clone https://github.com/theklic/RemoteToolbox.git
cd RemoteToolbox
python -m venv .venv && source .venv/bin/activate    # makes an isolated workspace
pip install -e .                                     # installs RemoteToolbox
```

<sub>The `venv` line creates a private little sandbox so this project's pieces
don't clash with anything else on your computer. See the
[Glossary](docs/GLOSSARY.md#virtual-environment-venv).</sub>

### Step 3 — Give it its first tool

Tools live in a folder called `tools/`. Copy in the bundled "hello" example:

```bash
cp -r examples/tools/hello tools/hello
```

### Step 4 — Create your settings files and run it

```bash
cp .env.example .env                 # for secret stuff (passwords, tokens)
cp config.example.yaml config.yaml   # for normal settings
python -m remotetoolbox              # start it! (chats in your terminal)
```

Now try chatting:

```
you ›  say hello to Sam
bot ›  Hello, Sam! 👋
```

🎉 That's a working AI agent calling a tool you control. **Type `/quit` to exit.**

### Step 5 — (Optional) Chat from your phone with Telegram

Once the terminal version works, you can reach it from anywhere via a Telegram
bot. It takes about 5 more minutes (make a bot, paste in a token, flip one
setting). The step-by-step is in
[**docs/DEPLOYMENT.md**](docs/DEPLOYMENT.md#5-create-the-telegram-bot).

> **Hit a snag in any step?** See [Troubleshooting](docs/DEPLOYMENT.md#troubleshooting).

---

## Making your own tool

A tool is just a small Python function with one special line (`@tool`) above it.
Drop the file in `tools/`, restart, and the AI can use it.

```python
# tools/weather/tool.py
from remotetoolbox import tool

@tool(description="Get the current weather for a city.")
def get_weather(city: str) -> str:
    # ...your code: call a weather website, read a sensor, whatever...
    return f"It's 21°C and sunny in {city}."
```

Restart and ask *"what's the weather in Oslo?"* — the AI figures out it should
call `get_weather("Oslo")` and tells you the answer.

👉 The full, friendly guide (passwords, more examples, do's and don'ts) is
[**docs/WRITING_TOOLS.md**](docs/WRITING_TOOLS.md). **Start here to build things.**

---

## Don't want to write code? Let an AI do it

This project is deliberately set up so an AI coding assistant can build tools for
you. Open the folder in [Claude Code](https://claude.com/code) and just describe
what you want:

> *"Add a tool that turns my living-room lights off using the Philips Hue API."*

It reads [CLAUDE.md](CLAUDE.md) (a guide written for AI assistants), follows the
project's conventions, and drops a working tool into `tools/`. You review it and
restart. That's the "vibe-coding" workflow this project is built around.

---

## Documentation

Docs are split by **who they're for**. Start with whichever matches you:

| Doc | Who it's for | What's in it |
|-----|--------------|--------------|
| [Glossary](docs/GLOSSARY.md) | 🐣 **Beginners** | Plain-English definitions of every term (AI, model, tool, MCP…). |
| [Writing Tools](docs/WRITING_TOOLS.md) | 🔧 **Tool makers** | How to build tools. The main "how do I add stuff" guide. |
| [Deployment](docs/DEPLOYMENT.md) | 🏠 **Home-server setup** | Full install, Telegram, running it 24/7, troubleshooting. |
| [Security](docs/SECURITY.md) | 🔒 **Everyone** | Keeping passwords safe and controlling who can use your bot. |
| [Architecture](docs/ARCHITECTURE.md) | 🛠️ **Developers** | How the internals fit together. |
| [Chat Adapters](docs/CHAT_ADAPTERS.md) | 🛠️ **Developers** | Add a new chat app (Discord, Matrix, …). |
| [CLAUDE.md](CLAUDE.md) | 🤖 **AI assistants** | Conventions for AI tools extending this project (machine-facing). |

---

## Project status

Early but working framework. The core pieces (how you write a tool, the AI
connection, the chat connection) are stable; the rest is meant to be forked and
tinkered with. Contributions to the **framework and docs** are welcome — just
remember that **tools themselves are never committed here**, they live on your
own machine.

## License

[MIT](LICENSE) — free to use, change, and share.
