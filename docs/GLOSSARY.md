# Glossary (plain English)

New to this world? Here's what the words mean, without the jargon. You don't need
to know all of these to start — come back when a term trips you up.

---

### AI agent / agent

A program that uses an AI model to *decide what to do* and then *do it* by calling
tools — not just chat. RemoteToolbox is a small, personal AI agent: you talk to
it, and it can take actions using the tools you gave it.

### LLM (Large Language Model)

The "brain" — the AI that understands your messages and writes replies. "Large
language model" is the technical name; this doc just calls it "the AI" or "the
model." Examples: Llama, Qwen, Mistral.

### <a name="model"></a>Model

One specific AI brain you can download and run, like `llama3.1` or `qwen2.5`.
Different models have different sizes and skills. For RemoteToolbox you want one
that supports **tool calling** (see below). Bigger models are smarter but need a
more powerful computer. `llama3.1` is a good starting point.

### Local / "runs locally"

It runs on *your own computer*, not on a company's servers over the internet.
That's the whole point here: your AI and your tools stay private to you.

### <a name="ollama"></a>Ollama

A free app that makes running an AI model on your own computer easy. You install
it, run `ollama pull <model>` once to download a model, and it quietly serves
that model to RemoteToolbox in the background. No account, no internet needed
after the download. → [ollama.com](https://ollama.com)

### Tool

A small piece of code that does one job — check the weather, turn off a light,
read a note. You write tools (or have an AI write them). The AI can *call* your
tools when it decides they'd help answer you. In RemoteToolbox a tool is a Python
function with `@tool` written above it.

### Tool calling (a.k.a. function calling)

The AI's ability to say *"I should run the `get_weather` tool with city =
Oslo"* instead of just guessing an answer. Not every model can do this — you need
a tool-capable model (most modern ones are). It's what lets the AI actually *do*
things rather than only talk.

### <a name="mcp"></a>MCP (Model Context Protocol)

A shared standard for connecting AI models to tools and data. Think of it like a
USB port for AI tools: if something speaks "MCP," lots of different AI apps can
plug into it. RemoteToolbox lets your tools work this way and can also connect to
*other* people's existing MCP tools. **You can ignore MCP entirely when starting**
— your own simple tools don't require knowing anything about it.

### Chat adapter / frontend

The chat app you actually type into. RemoteToolbox comes with two:
- **console** — chatting in your computer's terminal (simplest, no setup).
- **telegram** — chatting from your phone via a Telegram bot (remote access).

"Adapter" just means the connector that plugs a chat app into RemoteToolbox.

### Telegram bot / BotFather

Telegram lets anyone create an automated account called a "bot." You make one by
messaging a built-in helper called **@BotFather**, which gives you a secret
**token** (a long password). RemoteToolbox uses that token to send and receive
your messages.

### Token

A long secret string that acts like a password for a service (your Telegram bot,
a weather website's API, etc.). Tokens go in your `.env` file and are **never**
shared or uploaded. If one leaks, you cancel it and make a new one.

### The orchestrator (the "agent loop")

The part of RemoteToolbox that runs the conversation: it takes your message,
shows it to the AI along with the list of available tools, runs any tools the AI
asks for, and sends you the final answer. You rarely need to touch it — it just
works in the background.

### <a name="terminal"></a>Terminal / command line

The text window where you type commands (Terminal on Mac/Linux, PowerShell or
Command Prompt on Windows). Most setup steps are copy-paste commands here.

### <a name="virtual-environment-venv"></a>Virtual environment (venv)

A private sandbox for one project's Python pieces, so they don't clash with other
software on your computer. You create it once with
`python -m venv .venv` and "enter" it with `source .venv/bin/activate`. When it's
active, anything you install stays neatly inside this project.

### `pip install`

`pip` is Python's tool for installing software packages. `pip install -e .` tells
it to install RemoteToolbox itself (the `.` means "this folder").

### `.env` and `config.yaml`

Two settings files you create by copying the provided `*.example` versions:
- **`.env`** holds **secrets** (tokens, passwords). Never shared.
- **`config.yaml`** holds **normal settings** (which model, which chat app).

Both are kept off the internet automatically (they're "gitignored" — see below).

### Gitignored / "stays on your computer"

"Git" is how this project's code is stored and shared online. A **gitignored**
file is one git is told to *ignore* — it never gets uploaded. Your tools and
secrets are gitignored, so they live only on your machine. This is a core promise
of the project; see [SECURITY.md](SECURITY.md).

### Repository (repo)

A project's folder of code, tracked by git. "This repo" = the RemoteToolbox
project you downloaded.

### Framework

Reusable plumbing you build *on top of*. RemoteToolbox is a framework: it gives
you the chat + AI + tool-wiring, and you add your own tools to it.

---

Still stuck on a word? Open the project in [Claude Code](https://claude.com/code)
and just ask — *"what does &lt;word&gt; mean in this project?"*
