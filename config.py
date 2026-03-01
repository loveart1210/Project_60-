"""
Centralized configuration for the Multi-Agent Vietnamese Summarization System.
Update MODEL paths to match your local GGUF file locations.
"""
import os

# ---------------------------------------------------------------------------
# Project root (this file's directory)
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# ---------------------------------------------------------------------------
# Qwen2.5-3B-Instruct Q8_0 (Agent Reasoning - Downgraded for Stability)
AGENT_MODEL_REPO = "Qwen/Qwen2.5-3B-Instruct-GGUF"
AGENT_MODEL_FILES = [
    "qwen2.5-3b-instruct-q8_0.gguf"
]

# Qwen2.5-3B-Instruct Q8_0 (Summarization)
SUMMARIZER_MODEL_REPO = "Qwen/Qwen2.5-3B-Instruct-GGUF"
SUMMARIZER_MODEL_FILE = "qwen2.5-3b-instruct-q8_0.gguf"

# ---------------------------------------------------------------------------
# LLM generation parameters
# ---------------------------------------------------------------------------
AGENT_LLM_PARAMS = {
    "n_ctx": 8192,           # context window
    "n_gpu_layers": -1,      # Khôi phục về -1
    "verbose": False,
    "temperature": 0.3,
    "max_tokens": 2048,
    "top_p": 0.9,
    "repeat_penalty": 1.2,
}

SUMMARIZER_LLM_PARAMS = {
    "n_ctx": 4096,
    "n_gpu_layers": -1,      # Switch to e.g. 15 if you get out-of-memory errors
    "verbose": False,
    "temperature": 0.4,
    "max_tokens": 1024,
    "top_p": 0.9,
    "repeat_penalty": 1.2,
}

# ---------------------------------------------------------------------------
# Compression policy
# ---------------------------------------------------------------------------
INPUT_MIN_WORDS = 600
INPUT_MAX_WORDS = 1500
OUTPUT_MIN_WORDS = 180
OUTPUT_MAX_WORDS = 250
MAX_COMPRESSION_RATIO = 0.20   # output ≤ 20% of input

# ---------------------------------------------------------------------------
# Workflow limits
# ---------------------------------------------------------------------------
MAX_PLANNING_ITERATIONS = 3    # max Planner→Obs→Reflect loops
MAX_EXECUTION_RETRIES = 2      # max retries per execution step
MAX_CHUNK_WORDS = 300          # target words per chunk for hierarchical summarization

# ---------------------------------------------------------------------------
# Data file paths
# ---------------------------------------------------------------------------
SESSION_FILE = os.path.join(DATA_DIR, "session.json")
ROADMAP_VERSIONS_FILE = os.path.join(DATA_DIR, "roadmap_versions.json")
ROADMAP_FINAL_FILE = os.path.join(DATA_DIR, "roadmap_final.json")
EXECUTION_LOG_FILE = os.path.join(DATA_DIR, "execution_log.json")
OUTPUT_FILE = os.path.join(DATA_DIR, "output.json")
