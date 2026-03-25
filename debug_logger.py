"""
Debug Logger – Captures every step's input/output for NoneType diagnosis.

Writes all logs to a JSON file (data/debug_log.json) with:
  • timestamp, step_name, agent_name, phase
  • input_summary, output_data, output_type, is_none
  • error (if any)
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import config


class DebugLogger:
    """Centralized debug logger for the multi-agent pipeline."""

    _instance: Optional["DebugLogger"] = None

    def __new__(cls) -> "DebugLogger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._logs: List[Dict[str, Any]] = []
        return cls._instance

    @property
    def logs(self) -> List[Dict[str, Any]]:
        return self._logs

    def log_step(
        self,
        *,
        step_name: str,
        agent_name: str,
        phase: str = "unknown",
        input_summary: Optional[str] = None,
        output_data: Any = None,
        error: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a single pipeline step."""
        output_type = type(output_data).__name__

        # Truncate large outputs to keep the log manageable
        serializable_output = self._make_serializable(output_data)

        entry: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "step_name": step_name,
            "agent_name": agent_name,
            "phase": phase,
            "input_summary": (input_summary or "")[:500],
            "output_data": serializable_output,
            "output_type": output_type,
            "is_none": output_data is None,
            "error": error,
        }
        if extra:
            entry["extra"] = self._make_serializable(extra)

        self._logs.append(entry)

        # Also print a concise line for immediate console feedback
        none_flag = " ⚠️ OUTPUT IS NONE!" if output_data is None else ""
        print(f"  [DEBUG-LOG] {step_name} | {agent_name} | type={output_type}{none_flag}")

    def save(self, filepath: Optional[str] = None) -> str:
        """Write all logs to a JSON file and return the path."""
        filepath = filepath or config.DEBUG_LOG_FILE
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        payload = {
            "generated_at": datetime.now().isoformat(),
            "total_entries": len(self._logs),
            "none_count": sum(1 for e in self._logs if e["is_none"]),
            "logs": self._logs,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        print(f"\n📄 Debug log saved to: {filepath}")
        print(f"   Total entries: {payload['total_entries']}")
        print(f"   None outputs:  {payload['none_count']}")
        return filepath

    def reset(self) -> None:
        """Clear all logs (useful between runs)."""
        self._logs.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_serializable(self, obj: Any, max_str_len: int = 2000) -> Any:
        """Convert an object to a JSON-serializable form."""
        if obj is None:
            return None
        if isinstance(obj, (bool, int, float)):
            return obj
        if isinstance(obj, str):
            return obj[:max_str_len] + ("…" if len(obj) > max_str_len else "")
        if isinstance(obj, dict):
            return {k: self._make_serializable(v, max_str_len) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._make_serializable(item, max_str_len) for item in obj]
        # Fallback: convert to string
        s = str(obj)
        return s[:max_str_len] + ("…" if len(s) > max_str_len else "")
