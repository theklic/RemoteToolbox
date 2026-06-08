# RemoteToolbox documentation

The docs are written in **layers** so you can go exactly as deep as you need —
and stop when you have your answer.

```
 Layer 1 — GET GOING          ┐  Skim, point your coding agent here, build.
   README · CLAUDE.md         │  "I just want it running."
                              ┘
 Layer 2 — GUIDES            ┐   Task-focused how-tos.
   Writing Tools · Deployment │  "I'm doing a specific thing."
   Security · Chat Adapters   ┘
                              ┐
 Layer 3 — REFERENCE          │  Exact, exhaustive answers.
   Configuration · Reference  │  "I'm stuck / I need the precise contract /
   Architecture · Troublesh.  ┘   my agent needs to look something up."
```

You do **not** have to read these in order. Most people live in Layer 1, drop
into a Layer 2 guide when building something, and only open Layer 3 when stuck or
when their coding agent needs an authoritative answer.

---

## Pointing a coding agent at this project

If you're going to "vibe-code" with an AI assistant, point it here:

1. **[`CLAUDE.md`](../CLAUDE.md)** (repo root) — the machine-facing brief. It tells
   the agent the project conventions, the #1 task pattern ("add a tool that…"),
   the layout, and the git rules. Most agents read it automatically.
2. **[`WRITING_TOOLS.md`](WRITING_TOOLS.md)** — how tools are authored.
3. **[`REFERENCE.md`](REFERENCE.md)** and **[`CONFIGURATION.md`](CONFIGURATION.md)** —
   the exact contracts and settings the agent looks things up in.

A good opening prompt: *"Read CLAUDE.md and docs/REFERENCE.md, then add a tool
that …"*. Everything an agent needs to answer "how does X work here?" is in
Layer 3 with exact identifiers and error strings (so it's greppable).

---

## Find what you need by goal

| I want to… | Go to |
|---|---|
| Understand what this is, in plain words | [README](../README.md) · [Glossary](GLOSSARY.md) |
| Get it running on my machine | [README → Quickstart](../README.md#quickstart-about-10-minutes) |
| Run it 24/7 / reach it from my phone | [Deployment](DEPLOYMENT.md) |
| Build a tool | [Writing Tools](WRITING_TOOLS.md) |
| Know every config option | [Configuration](CONFIGURATION.md) |
| Know the exact API / contracts | [Reference](REFERENCE.md) |
| Decode an error message | [Reference → Error & message reference](REFERENCE.md#error--message-reference) |
| Keep secrets safe / control access | [Security](SECURITY.md) |
| Understand the internals | [Architecture](ARCHITECTURE.md) |
| Add a new chat app (Discord, etc.) | [Chat Adapters](CHAT_ADAPTERS.md) |
| Add a new model backend | [Architecture → Extension points](ARCHITECTURE.md#the-three-extension-points) |
| Look up a word | [Glossary](GLOSSARY.md) |

---

## The full doc set

| Doc | Layer | Audience |
|-----|-------|----------|
| [README](../README.md) | 1 | Everyone — start here |
| [Glossary](GLOSSARY.md) | 1 | Beginners |
| [CLAUDE.md](../CLAUDE.md) | 1 | AI coding assistants (machine-facing) |
| [Writing Tools](WRITING_TOOLS.md) | 2 | Tool makers |
| [Deployment](DEPLOYMENT.md) | 2 | Home-server / operators |
| [Security](SECURITY.md) | 2 | Everyone |
| [Chat Adapters](CHAT_ADAPTERS.md) | 2 | Developers |
| [Configuration](CONFIGURATION.md) | 3 | Operators, agents |
| [Reference](REFERENCE.md) | 3 | Tool makers, developers, agents |
| [Architecture](ARCHITECTURE.md) | 3 | Developers |

> **Keeping docs honest (enforced):** the Layer 3 reference docs mirror the code
> in [`src/remotetoolbox/`](../src/remotetoolbox/). This isn't just a convention —
> [`tests/test_docs_sync.py`](../tests/test_docs_sync.py) fails CI if:
> - a config field in `config.py` isn't documented in
>   [CONFIGURATION.md](CONFIGURATION.md) (key **and** default), or
> - any internal doc link or `#anchor` doesn't resolve.
>
> So when you change a contract, default, or error message, update
> [REFERENCE.md](REFERENCE.md) / [CONFIGURATION.md](CONFIGURATION.md) in the same
> commit, or `pytest` will tell you which one you missed.
