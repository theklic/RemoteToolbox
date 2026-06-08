# Your tools live here 🔒

Everything in this folder (except this README and `.gitkeep`) is **gitignored**.
Your tools and their logic are private to your machine and are never committed
to the RemoteToolbox repo. That is by design — see [`../docs/SECURITY.md`](../docs/SECURITY.md).

## Add a tool

Drop a Python file anywhere under this directory:

```python
# tools/hello/tool.py
from remotetoolbox import tool

@tool(description="Greet someone by name.")
def hello(name: str) -> str:
    return f"Hello, {name}! 👋"
```

Then restart RemoteToolbox. On startup it scans this folder, runs the `@tool`
decorators, and exposes everything it finds to the agent.

## Copy an example to get started

```bash
cp -r ../examples/tools/hello ./hello
```

## Rules of thumb

- One capability per function. Small, focused tools work best with small models.
- Write a clear `description=` and use type hints — that's what the LLM reads.
- Read secrets from the environment (`os.environ`), never hardcode them here.
- Files/dirs starting with `_` are skipped by the loader (handy for helpers).

Full guide: [`../docs/WRITING_TOOLS.md`](../docs/WRITING_TOOLS.md).
