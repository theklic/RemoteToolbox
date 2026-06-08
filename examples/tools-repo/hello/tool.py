"""Starter tool for your private tools repo. Copy/rename this folder for your own.

See docs/WRITING_TOOLS.md in the RemoteToolbox repo for the full guide.
"""

from remotetoolbox import tool


@tool(description="Greet someone by name.")
def hello(name: str) -> str:
    """Return a friendly greeting.

    name: The person to greet.
    """
    return f"Hello, {name}! 👋"
