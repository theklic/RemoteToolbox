# Writing tools

This is the guide you'll spend the most time in. A "tool" is a Python function
the agent can call. You write it, drop it in `./tools`, restart, and chat to it.

> Everything under `./tools` is **gitignored**. Your tools and their secrets stay
> on your machine. See [SECURITY.md](SECURITY.md). To keep version history and a
> changelog for your tools (in their own git repo), see
> [MANAGING_TOOLS.md](MANAGING_TOOLS.md).

> 💡 **Looking for things to build against?** The community-maintained
> [public-apis/public-apis](https://github.com/public-apis/public-apis) list is a
> great catalogue of free APIs — weather, transit, finance, fun — and many need
> **no API key at all**, so you can wire up a tool in minutes. For the ones that
> do, put the key in `.env` (see [Secrets & credentials](#secrets--credentials)).

## The shape of a tool

```python
# tools/weather/tool.py
from remotetoolbox import tool

@tool(description="Get the current weather for a city.")
def get_weather(city: str) -> str:
    """Look up current conditions.

    city: The city name, e.g. "Oslo".
    """
    # ... your logic ...
    return "21°C and sunny in Oslo."
```

What each part does:

- **`@tool(...)`** registers the function so the loader finds it.
- **`description=`** is the one-line summary the LLM reads to decide *whether* to
  call your tool. Make it concrete. If you omit it, the first line of the
  docstring is used.
- **Type hints** (`city: str`) become the JSON schema the LLM uses to build
  arguments. Always annotate your parameters.
- **Docstring `name: ...` lines** become per-argument descriptions for the LLM.
- **The return value** is sent back to the model. Return a `str` for prose, or a
  `dict`/`list` (auto-serialized to JSON) for structured data.

## Where to put files

- Anywhere under a directory listed in `config.yaml` → `tools.paths` (default
  `./tools`). The loader scans **recursively**.
- One folder per tool (or per group) keeps things tidy, but any layout works.
- Files/folders starting with `_` are **skipped** by discovery — use them for
  shared helper code. The loader puts each tool file's own directory on the
  import path, so a tool can import a **sibling** helper by name:

  ```
  tools/
  ├── weather/
  │   ├── tool.py        # @tool functions  (loaded)
  │   └── _client.py     # helper, NOT scanned but importable from tool.py
  ```

  ```python
  # tools/weather/tool.py
  from _client import fetch          # imports the sibling _client.py
  ```

  Helper modules are imported by **bare name and cached globally**, so keep their
  names unique across your tool folders (e.g. `_weather_client.py`, not a generic
  `_client.py` in every folder).
- Multiple `@tool` functions per file is fine.

## Supported parameter types

The schema generator understands the common cases:

| Python annotation | JSON schema |
|---|---|
| `str` | `string` |
| `int` | `integer` |
| `float` | `number` |
| `bool` | `boolean` |
| `list[str]` | `array` of strings |
| `dict` | `object` |
| `Optional[X]` / `X = default` | not required |

Parameters with no default and not `Optional` are marked **required**.

### Need a richer schema?

Pass it explicitly and skip auto-generation:

```python
@tool(
    name="set_timer",
    description="Start a countdown timer.",
    parameters={
        "type": "object",
        "properties": {
            "minutes": {"type": "integer", "minimum": 1, "maximum": 180},
            "label": {"type": "string"},
        },
        "required": ["minutes"],
    },
)
def set_timer(minutes: int, label: str = "timer") -> str:
    ...
```

## Async tools

Just declare `async def` — the orchestrator awaits it. Sync tools are
automatically run in a thread, so blocking I/O won't stall the chat loop either
way.

```python
@tool(description="Fetch a URL and return its title.")
async def page_title(url: str) -> str:
    import httpx
    async with httpx.AsyncClient() as c:
        r = await c.get(url)
    # ... parse ...
    return title
```

## Secrets & credentials

**Never hardcode secrets in a tool file.** Read them from the environment, which
you populate via `.env` (gitignored):

```python
import os

@tool(description="Send myself a push notification.")
def notify(message: str) -> str:
    token = os.environ.get("PUSHOVER_TOKEN")
    if not token:
        return "PUSHOVER_TOKEN isn't set — add it to .env."   # friendly, not a crash
    ...
    return "Sent."
```

> Using `os.environ.get(...)` and returning a clear message is gentler than
> `os.environ["X"]`, which raises a `KeyError` — that's safely caught and shown
> to the model, but it logs a full traceback for a routine "you forgot to set it".

Add the variable to `.env`:

```
PUSHOVER_TOKEN=abc123
```

See [SECURITY.md](SECURITY.md) for the full reasoning.

## Errors are safe

If your tool raises, the orchestrator catches it and hands the error text to the
model (it doesn't crash the bot). The model can then apologize or try a different
approach. You can also return an error string yourself for expected failures:

```python
@tool(description="Read a note by name.")
def read_note(name: str) -> str:
    path = NOTES_DIR / f"{name}.md"
    if not path.exists():
        return f"No note named {name!r}."
    return path.read_text()
```

## Proactive messages (digests, alerts)

Normally a tool runs because the user asked something. But a tool can also send a
message **unprompted** — a morning digest, a "backup finished" ping, a sensor
alert. The framework gives you one primitive; **your tool decides when and why**
to use it (RemoteToolbox has no built-in scheduler).

```python
from remotetoolbox import notify, notify_agent, tool

@tool(description="Send myself a reminder now.")
def remind_me(text: str) -> str:
    notify(f"⏰ {text}")            # a message YOU composed
    return "Sent."
```

- `notify(text, to=None)` — push `text` to a chat. `to` defaults to the adapter's
  default chat (for Telegram, your first allowed user). Pass `to="<chat_id>"` to
  target a specific chat.
- `notify_agent(prompt, to=None)` — let the **agent** compose the message: it runs
  `prompt` through the LLM and your other tools, then sends the reply. Great for
  digests:

  ```python
  notify_agent("Write my morning digest using the weather and calendar tools.")
  ```

  It runs in a **separate conversation** from your interactive chat, so a daily
  digest won't clutter or skew your normal back-and-forth. Pass
  `share_history=True` if you *want* it to use the interactive context.

Both are **fire-and-forget** and **thread-safe**, so you can call them from a
background timer your tool starts. A self-scheduling "07:00 digest" pattern using
`threading.Timer` is in [`examples/tools/proactive/`](../examples/tools/proactive/).

> Outbound delivery only works while RemoteToolbox is **running** with a chat
> adapter. To send a message: for a DM the `chat_id` is your Telegram user ID
> (the one in `RTB_ALLOWED_USERS`), and you must have messaged the bot once.
> Tools are trusted code — be deliberate about what you push. See
> [SECURITY.md](SECURITY.md).

## Designing tools small models can use

You'll likely run a smaller local model. Help it succeed:

- **One job per tool.** `lights_on` / `lights_off`, not `control(device, action)`.
- **Few parameters**, clearly named, with descriptions.
- **Concrete descriptions**: "Turn the living-room lights off" beats "control lights".
- **Return short, clear results.** Long blobs confuse small models.
- Pick an Ollama model that supports tool calling (e.g. `llama3.1`, `qwen2.5`,
  `mistral-nemo`). Set it in `config.yaml` → `llm.ollama.model`.

## Reusing existing MCP servers (optional)

If you already run an [MCP](https://modelcontextprotocol.io) server, list it in
`config.yaml` and its tools appear alongside your native ones:

```yaml
tools:
  paths: [./tools]
  mcp_servers:
    - name: filesystem
      command: npx
      args: ["-y", "@modelcontextprotocol/server-filesystem", "/srv/shared"]
```

Install the extra: `pip install -e ".[mcp]"`. Native `@tool` functions take
precedence if names collide.

## Testing a tool without the LLM

Your tool is a normal function — call it directly:

```python
from tools.weather.tool import get_weather   # if importable
print(get_weather("Oslo"))
```

Or use the console adapter (`python -m remotetoolbox`) and just ask for it. The
console needs no tokens and is the fastest feedback loop.

## Checklist

- [ ] Function decorated with `@tool(description=...)`
- [ ] All parameters type-hinted
- [ ] Docstring describes each parameter (`name: ...`)
- [ ] Secrets read from `os.environ`, added to `.env`
- [ ] Returns a short, clear string (or JSON-able dict/list)
- [ ] Lives under `./tools`, restart to load
