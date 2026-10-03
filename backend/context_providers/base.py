"""The interface every context provider implements.

A context provider plugs an outside source of information (weather, calendar...) into the chat
without the chat knowing anything about it. It contributes:

    tools()  -> tools the model can call when it needs the information (nothing is fetched or
                sent to the model unless it actually asks)
    prompt() -> a short system-prompt section explaining when and how to use them
"""

from typing import List


class ContextProvider:
    """Base class: subclass it, then register an instance in context_providers/__init__.py."""

    name: str = "base"

    def is_enabled(self) -> bool:
        """Whether this provider is configured and should be offered to the model."""
        return True

    def tools(self) -> List:
        """Tools (e.g. @beta_tool functions) the model can call."""
        return []

    def prompt(self) -> str:
        """Instructions for the system prompt (keep them short)."""
        return ""
