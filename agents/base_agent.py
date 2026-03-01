"""
Base Agent – Abstract base class for all agents in the multi-agent system.

Every agent follows the same pattern:
  1. Receive a *context* dict
  2. Build prompt from role template + context
  3. Call LLM
  4. Parse response
  5. Return structured result
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from llm_loader import LLMManager, parse_json_from_text


class BaseAgent(ABC):
    """Abstract base for every agent."""

    def __init__(self, name: str, role_description: str) -> None:
        self.name = name
        self.role_description = role_description
        self.llm = LLMManager()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @abstractmethod
    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent's task and return a structured result."""
        ...

    # ------------------------------------------------------------------
    # Helpers available to subclasses
    # ------------------------------------------------------------------

    def _call_llm(
        self,
        user_prompt: str,
        *,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
    ) -> str:
        """Send a prompt to the currently loaded LLM and return raw text."""
        sys = system_prompt or self._default_system_prompt()
        return self.llm.generate(
            user_prompt, 
            system_prompt=sys, 
            max_tokens=max_tokens,
            stop=stop
        )

    def _call_llm_json(
        self,
        user_prompt: str,
        *,
        system_prompt: str = None,
        max_tokens: int = None,
    ) -> Dict[str, Any]:
        """Call LLM and parse the response as JSON."""
        # Add stop sequence to prevent trailing garbage after JSON
        raw = self._call_llm(user_prompt, system_prompt=system_prompt, max_tokens=max_tokens)
        try:
            return parse_json_from_text(raw)
        except (json.JSONDecodeError, ValueError):
            # Return raw text wrapped in a dict so callers can still proceed
            return {"raw_response": raw, "_parse_error": True}

    def _default_system_prompt(self) -> str:
        return (
            f"Bạn là {self.name}. {self.role_description}\n"
            "Luôn trả lời bằng tiếng Việt. "
            "Khi được yêu cầu trả về JSON, hãy chỉ trả về JSON hợp lệ, "
            "không thêm giải thích bên ngoài block JSON."
        )

    def _truncate_text(self, text: str, max_chars: int = 3000) -> str:
        """Truncate text to fit within a context-window-friendly size."""
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "\n… [đã cắt bớt]"
