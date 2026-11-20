"""Agent module for PatchPal.

This module contains the agent implementations:
- function_calling.py: Standard agent with native function calling
- react.py: ReAct agent for models without native function calling
- tiny.py: Function-calling agent tuned for small context windows
"""

# Re-export main functions for convenience
from patchpal.agent.function_calling import PatchPalAgent, create_agent
from patchpal.agent.react import ReActAgent, create_react_agent
from patchpal.agent.tiny import TinyAgent, create_tiny_agent

__all__ = [
    "create_agent",
    "create_react_agent",
    "create_tiny_agent",
    "PatchPalAgent",
    "ReActAgent",
    "TinyAgent",
]
