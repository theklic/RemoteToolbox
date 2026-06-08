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

## Keep a version history of your tools

Because this folder is ignored by the toolbox repo, you can make it (or a
separate folder you point `tools.paths` at) **its own git repo** — giving you
history, a changelog, and rollback when you break something. The recommended
setup keeps your tools in a separate repo entirely.

→ [`../docs/MANAGING_TOOLS.md`](../docs/MANAGING_TOOLS.md), with a copyable
starter at [`../examples/tools-repo/`](../examples/tools-repo/).

---

Writing guide: [`../docs/WRITING_TOOLS.md`](../docs/WRITING_TOOLS.md).
