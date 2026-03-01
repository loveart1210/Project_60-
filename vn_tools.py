"""
Vietnamese Text Processing Tools – built on top of *underthesea*.

Provides:
  • word counting (Vietnamese-aware)
  • sentence splitting with sentence IDs
  • text chunking for hierarchical summarization
  • compression-target computation
"""

from __future__ import annotations

import re
from typing import Dict, List

from underthesea import word_tokenize, sent_tokenize

import config


# ------------------------------------------------------------------
# Word-level utilities
# ------------------------------------------------------------------

def count_words(text: str) -> int:
    """Count the number of Vietnamese words using underthesea tokenizer."""
    tokens = word_tokenize(text)
    # Filter out pure-punctuation tokens
    return sum(1 for t in tokens if re.search(r"\w", t))


# ------------------------------------------------------------------
# Sentence-level utilities
# ------------------------------------------------------------------

def split_sentences(text: str) -> List[Dict]:
    """Split *text* into sentences and annotate with sentence IDs.

    Returns a list of dicts:
        [{"sentence_id": 1, "text": "…"}, …]
    """
    raw_sents = sent_tokenize(text)
    sentences = []
    for idx, s in enumerate(raw_sents, start=1):
        s = s.strip()
        if s:
            sentences.append({"sentence_id": idx, "text": s})
    return sentences


# ------------------------------------------------------------------
# Chunking for hierarchical summarization
# ------------------------------------------------------------------

def chunk_text(
    sentences: List[Dict],
    max_chunk_words: int = config.MAX_CHUNK_WORDS,
) -> List[Dict]:
    """Group sentences into chunks that do not exceed *max_chunk_words*.

    Returns list of dicts:
        [
          {
            "chunk_id": 1,
            "sentence_ids": [1, 2, 3],
            "text": "combined text …",
            "word_count": 280
          },
          …
        ]
    """
    chunks: List[Dict] = []
    current_sents: List[Dict] = []
    current_words = 0
    chunk_id = 1

    for sent in sentences:
        sent_wc = count_words(sent["text"])
        if current_sents and (current_words + sent_wc) > max_chunk_words:
            # Flush current chunk
            chunks.append(_make_chunk(chunk_id, current_sents, current_words))
            chunk_id += 1
            current_sents = []
            current_words = 0
        current_sents.append(sent)
        current_words += sent_wc

    # Flush remaining
    if current_sents:
        chunks.append(_make_chunk(chunk_id, current_sents, current_words))

    return chunks


def _make_chunk(chunk_id: int, sents: List[Dict], word_count: int) -> Dict:
    return {
        "chunk_id": chunk_id,
        "sentence_ids": [s["sentence_id"] for s in sents],
        "text": " ".join(s["text"] for s in sents),
        "word_count": word_count,
    }


# ------------------------------------------------------------------
# Compression policy
# ------------------------------------------------------------------

def compute_compression_target(input_word_count: int) -> Dict[str, int]:
    """Return min/max output word counts following the compression policy.

    Rules:
      • Output 150–250 words.
      • Output ≤ 20% of input length.
    """
    ratio_limit = int(input_word_count * config.MAX_COMPRESSION_RATIO)
    max_words = min(config.OUTPUT_MAX_WORDS, ratio_limit)
    min_words = min(config.OUTPUT_MIN_WORDS, max_words)
    return {"min_words": min_words, "max_words": max_words}


def validate_input_length(text: str) -> bool:
    """Check if input length is within the allowed range (600-1500 words)."""
    wc = count_words(text)
    return config.INPUT_MIN_WORDS <= wc <= config.INPUT_MAX_WORDS
