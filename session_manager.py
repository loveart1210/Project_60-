"""
Session Manager – Persists workflow state to JSON files.

Managed files:
  • session.json            – current session state + history trace
  • roadmap_versions.json   – all roadmap drafts (v1, v2, …)
  • roadmap_final.json      – the finalized roadmap
  • execution_log.json      – steps attempted & outcomes (avoid repeating mistakes)
  • output.json             – final output
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import config


def _ensure_data_dir() -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)


def _load_json(path: str) -> Any:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_json(path: str, data: Any) -> None:
    _ensure_data_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class SessionManager:
    """Manages a single summarization session."""

    def __init__(self) -> None:
        self.session: Dict[str, Any] = {}
        self.roadmap_versions: Dict[str, Any] = {}
        self.roadmap_final: Optional[Dict[str, Any]] = None
        self.execution_log: List[Dict[str, Any]] = []
        self.data_store: Dict[str, Any] = {}
        # Stats counters
        self.stats = {
            "planner_loop": 0,
            "planner_observation_loop": 0,
            "planner_reflection_loop": 0,
            "execution_loop": 0,
            "execution_observation_loop": 0,
            "execution_reflection_loop": 0,
            "chunks": 0
        }

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(self, input_text: str, style: str) -> str:
        """Create a brand-new session and return the session_id."""
        sid = str(uuid.uuid4())[:8]
        self.session = {
            "session_id": sid,
            "current_phase": "planning",
            "iteration_count": 0,
            "roadmap_version": "v0",
            "last_decision": "",
            "confidence_score": 0.0,
            "style": style,
            "input_word_count": len(input_text.split()),
            "created_at": datetime.now().isoformat(),
            "history": [],
        }
        self.roadmap_versions = {}
        self.roadmap_final = None
        self.execution_log = []
        self.data_store = {}
        self.stats = {
            "planner_loop": 0,
            "planner_observation_loop": 0,
            "planner_reflection_loop": 0,
            "execution_loop": 0,
            "execution_observation_loop": 0,
            "execution_reflection_loop": 0,
            "chunks": 0
        }
        self.save_all()
        return sid

    def load_existing(self) -> bool:
        """Try to load an existing session. Returns True on success."""
        data = _load_json(config.SESSION_FILE)
        if data is None:
            return False
        self.session = data
        self.data_store = data.get("data_store", {})
        self.roadmap_versions = _load_json(config.ROADMAP_VERSIONS_FILE) or {}
        self.roadmap_final = _load_json(config.ROADMAP_FINAL_FILE)
        self.execution_log = _load_json(config.EXECUTION_LOG_FILE) or []
        self.stats = data.get("stats", {
            "planner_loop": 0,
            "planner_observation_loop": 0,
            "planner_reflection_loop": 0,
            "execution_loop": 0,
            "execution_observation_loop": 0,
            "execution_reflection_loop": 0,
            "chunks": 0
        })
        return True

    # ------------------------------------------------------------------
    # Session updates
    # ------------------------------------------------------------------

    def update_phase(self, phase_name: str, sequence_id: Optional[int] = None) -> None:
        """Update phase with optional sequence ID for granularity."""
        if sequence_id is not None:
            self.session["current_phase"] = f"{phase_name} ({sequence_id})"
        else:
            self.session["current_phase"] = phase_name
        self._save_session()

    def increment_stat(self, key: str) -> None:
        """Increment a loop counter or stat."""
        if key in self.stats:
            self.stats[key] += 1
            self._save_session()

    def set_decision(self, decision: str, confidence: float) -> None:
        self.session["last_decision"] = decision
        self.session["confidence_score"] = confidence
        self._save_session()

    def add_history(
        self,
        agent: str,
        action: str,
        result_summary: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry = {
            "agent": agent,
            "action": action,
            "timestamp": datetime.now().isoformat(),
            "result_summary": result_summary,
        }
        if details:
            entry["details"] = details
        self.session["history"].append(entry)
        self._save_session()

    # ------------------------------------------------------------------
    # Roadmap management
    # ------------------------------------------------------------------

    def save_roadmap_version(self, version_key: str, roadmap: Dict[str, Any]) -> None:
        """Save a roadmap draft under the given version key (e.g. 'v1')."""
        self.roadmap_versions[version_key] = roadmap
        self.session["roadmap_version"] = version_key
        self.session["iteration_count"] = int(version_key.replace("v", ""))
        _save_json(config.ROADMAP_VERSIONS_FILE, self.roadmap_versions)
        self._save_session()

    def finalize_roadmap(self, roadmap: Dict[str, Any]) -> None:
        self.roadmap_final = roadmap
        _save_json(config.ROADMAP_FINAL_FILE, roadmap)

    def get_latest_roadmap(self) -> Optional[Dict[str, Any]]:
        if self.roadmap_final:
            return self.roadmap_final
        if self.roadmap_versions:
            latest_key = sorted(self.roadmap_versions.keys())[-1]
            return self.roadmap_versions[latest_key]
        return None

    # ------------------------------------------------------------------
    # Data Store (Source of Truth for intermediate results)
    # ------------------------------------------------------------------

    def update_data_store(self, key: str, value: Any) -> None:
        """Save a specific result (e.g. 'refined_summary') to the session file immediately."""
        self.data_store[key] = value
        self.session["last_updated"] = datetime.now().isoformat()
        self._save_session()

    def get_data(self, key: str) -> Optional[Any]:
        """Retrieve a value from the persistent data store."""
        return self.data_store.get(key)

    # ------------------------------------------------------------------
    # Execution log
    # ------------------------------------------------------------------

    def log_execution_step(
        self,
        step_id: str,
        status: str,
        output_summary: str,
        error: Optional[str] = None,
    ) -> None:
        entry = {
            "step_id": step_id,
            "status": status,
            "output_summary": output_summary,
            "timestamp": datetime.now().isoformat(),
        }
        if error:
            entry["error"] = error
        self.execution_log.append(entry)
        _save_json(config.EXECUTION_LOG_FILE, self.execution_log)

    def get_failed_steps(self) -> List[Dict[str, Any]]:
        """Return all previously failed steps so agents can avoid repeating mistakes."""
        return [e for e in self.execution_log if e["status"] == "failed"]

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def save_output(self, output: Dict[str, Any]) -> None:
        _save_json(config.OUTPUT_FILE, output)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def save_all(self) -> None:
        _ensure_data_dir()
        self._save_session()
        _save_json(config.ROADMAP_VERSIONS_FILE, self.roadmap_versions)
        if self.roadmap_final:
            _save_json(config.ROADMAP_FINAL_FILE, self.roadmap_final)
        _save_json(config.EXECUTION_LOG_FILE, self.execution_log)

    def _save_session(self) -> None:
        self.session["data_store"] = self.data_store
        self.session["stats"] = self.stats
        _save_json(config.SESSION_FILE, self.session)
