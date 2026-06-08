"""The smallest possible RemoteToolbox tool. Copy this folder to ../../tools/
to try it:  cp -r examples/tools/hello tools/hello
"""

from remotetoolbox import tool


@tool(description="Greet someone by name.")
def hello(name: str) -> str:
    """Return a friendly greeting.

    name: The person to greet.
    """
    return f"Hello, {name}! 👋"
