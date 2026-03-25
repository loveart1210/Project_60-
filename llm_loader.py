"""
LLM Loader – Manages loading/unloading of GGUF models via llama-cpp-python.

Uses a singleton pattern so the whole application shares one model at a time.
Two model slots:
  • agent model  (Qwen2.5-7B-Q4)   - for Manager / Planner / Observation / Reflection
  • summarizer   (Qwen2.5-3B-Q8)   - for text summarization
"""

from __future__ import annotations

import json
import re
from typing import List, Optional

from llama_cpp import Llama
from huggingface_hub import hf_hub_download

import config
from debug_logger import DebugLogger


class LLMManager:
    """Singleton that keeps at most ONE model loaded to save VRAM."""

    _instance: Optional["LLMManager"] = None
    _model: Optional[Llama] = None
    _current_model_type: Optional[str] = None

    def __new__(cls) -> "LLMManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._model = None
            cls._instance._current_model_type = None  # "agent" | "summarizer"
        return cls._instance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_agent_model(self) -> None:
        """Load the 7B agent model (if not already loaded)."""
        if self._current_model_type == "agent":
            return
        self._unload()
        print(f"[LLMManager] Resolving agent model from HF: {config.AGENT_MODEL_REPO} ...")
        
        # Download all shards (Original Qwen Repo uses split GGUF)
        shards = []
        for filename in config.AGENT_MODEL_FILES:
            path = hf_hub_download(
                repo_id=config.AGENT_MODEL_REPO,
                filename=filename
            )
            shards.append(path)
        
        # Point to the first shard; llama-cpp handles subsequent shards if in the same dir
        self._model = Llama(
            model_path=shards[0],
            n_ctx=config.AGENT_LLM_PARAMS["n_ctx"],
            n_gpu_layers=config.AGENT_LLM_PARAMS["n_gpu_layers"],
            verbose=config.AGENT_LLM_PARAMS["verbose"],
        )
        self._current_model_type = "agent"
        print("[LLMManager] Agent model loaded.")

    def load_summarizer_model(self) -> None:
        """Load the 3B summarizer model (if not already loaded)."""
        if self._current_model_type == "summarizer":
            return
        self._unload()
        print(f"[LLMManager] Resolving summarizer model from HF: {config.SUMMARIZER_MODEL_REPO} ...")
        
        path = hf_hub_download(
            repo_id=config.SUMMARIZER_MODEL_REPO,
            filename=config.SUMMARIZER_MODEL_FILE
        )
        
        self._model = Llama(
            model_path=path,
            n_ctx=config.SUMMARIZER_LLM_PARAMS["n_ctx"],
            n_gpu_layers=config.SUMMARIZER_LLM_PARAMS["n_gpu_layers"],
            verbose=config.SUMMARIZER_LLM_PARAMS["verbose"],
        )
        self._current_model_type = "summarizer"
        print("[LLMManager] Summarizer model loaded.")

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stop: Optional[List[str]] = None,
    ) -> str:
        """Generate text using the currently loaded model.

        Uses the chat-completion API with Qwen instruct format.
        """
        if self._model is None:
            raise RuntimeError("No model loaded. Call load_agent_model() or load_summarizer_model() first.")

        # Pick defaults from the relevant config block
        params = (
            config.AGENT_LLM_PARAMS
            if self._current_model_type == "agent"
            else config.SUMMARIZER_LLM_PARAMS
        )
        _max_tokens = max_tokens or params["max_tokens"]
        _temperature = temperature if temperature is not None else params["temperature"]
        _top_p = top_p if top_p is not None else params["top_p"]

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self._model.create_chat_completion(
            messages=messages,
            max_tokens=_max_tokens,
            temperature=_temperature,
            top_p=_top_p,
            repeat_penalty=params.get("repeat_penalty", 1.2),
            stop=stop,
        )

        # --- Debug Logging ---
        debug = DebugLogger()
        raw_content = None
        try:
            raw_content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            debug.log_step(
                step_name="llm_generate_extract_content",
                agent_name="LLMManager",
                phase="llm_call",
                input_summary=prompt[:200],
                output_data=None,
                error=f"Failed to extract content from response: {e}",
                extra={"raw_response": str(response)[:1000]},
            )
            return ""

        if raw_content is None:
            debug.log_step(
                step_name="llm_generate",
                agent_name="LLMManager",
                phase="llm_call",
                input_summary=prompt[:200],
                output_data=None,
                error="LLM returned None content",
                extra={"raw_response": str(response)[:1000]},
            )
            return ""

        result = raw_content.strip()
        debug.log_step(
            step_name="llm_generate",
            agent_name="LLMManager",
            phase="llm_call",
            input_summary=prompt[:200],
            output_data=result,
        )
        return result

    def unload(self) -> None:
        """Public method to explicitly unload model and rest GPU."""
        self._unload()

    @property
    def current_model_type(self) -> Optional[str]:
        return self._current_model_type

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _unload(self) -> None:
        """Free the currently loaded model and rest the GPU."""
        if self._model is not None:
            model_type = self._current_model_type
            print(f"[LLMManager] Unloading {model_type} model …")
            
            # 1. Delete model reference
            del self._model
            self._model = None
            self._current_model_type = None
            
            # 2. Force garbage collection multiple times
            import gc
            gc.collect()
            gc.collect()
            
            # 3. Small rest period to let VRAM clear fully
            import time
            print(f"[LLMManager] Resting GPU for 2s (Stability) …")
            time.sleep(2)
            
            print(f"[LLMManager] {model_type} model unloaded.")


def parse_json_from_text(text: str) -> dict:
    """Extract and parse the first JSON object/array found in *text*.

    LLMs often wrap JSON in markdown fences; this helper handles that.
    """
    # Try to find ```json ... ``` block first
    match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)```", text)
    if match:
        candidate = match.group(1).strip()
    else:
        # Fall back: find first { … } or [ … ]
        brace = text.find("{")
        bracket = text.find("[")
        if brace == -1 and bracket == -1:
            raise ValueError("No JSON object found in LLM output.")
        start = min(p for p in (brace, bracket) if p >= 0)
        # Find matching close
        open_ch = text[start]
        close_ch = "}" if open_ch == "{" else "]"
        depth = 0
        end = start
        for i in range(start, len(text)):
            if text[i] == open_ch:
                depth += 1
            elif text[i] == close_ch:
                depth -= 1
                if depth == 0:
                    end = i
                    break
        candidate = text[start : end + 1]

    parsed = json.loads(candidate)
    debug = DebugLogger()
    debug.log_step(
        step_name="parse_json_from_text",
        agent_name="LLMManager",
        phase="json_parse",
        input_summary=text[:200],
        output_data=parsed,
    )
    return parsed
