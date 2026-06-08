# Example: `hello`

The minimal tool. Demonstrates the `@tool` decorator, a typed argument, and a
docstring whose `name:` line becomes the argument's description for the LLM.

## Try it

```bash
cp -r examples/tools/hello tools/hello
python -m remotetoolbox          # console adapter
```

Then: `say hello to Sam` → the model calls `hello("Sam")`.
