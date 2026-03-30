"""
Execution Agent – Carries out each step of the roadmap.

Responsible for:
  1. Sentence splitting & chunking (via vn_tools)
  2. Chunk-level summarization (via 3B summarizer model)
  3. Merging chunk summaries
  4. Global refinement
  5. Verification (claim ↔ source matching)
  6. Style editing

The agent executes ONE step at a time (controlled by Manager).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from debug_logger import DebugLogger
import vn_tools


class ExecutionAgent(BaseAgent):

    def __init__(self) -> None:
        super().__init__(
            name="Execution Agent",
            role_description=(
                "Agent thực thi nhiệm vụ tóm tắt văn bản tiếng Việt. "
                "Bạn thực hiện từng bước trong roadmap: chunking, tóm tắt, "
                "merge, refinement, kiểm chứng, và hiệu chỉnh phong cách."
            ),
        )

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch to the appropriate step handler.

        context must contain:
          • current_step : dict   – the roadmap step to execute
          • input_text   : str    – original Vietnamese text
          • style        : str    – "news_brief" | "academic_abstract"
          • sentences    : list   – pre-split sentences (from previous step or None)
          • chunks       : list   – pre-computed chunks (or None)
          • chunk_summaries : list – summaries from chunk step (or None)
          • merged_summary : str  – merged summary (or None)
          • refined_summary: str  – refined summary (or None)
          • failed_steps : list   – previously failed steps (to avoid repeating)
        """
        step = context["current_step"]
        step_name = step.get("name", "").lower()
        tool = step.get("tool", "")
        if not tool or not isinstance(tool, str):
            tool = ""
        tool = tool.lower()
        
        step_id = step.get("step_id", "unknown")
        debug = DebugLogger()

        # 🏆 Robust Tool-based Routing (Use Planner's specified tool first)
        if "tách câu" in step_name or "sent_tokenize" in tool:
            result = self._step_split_sentences(context)
        elif "chunk_text" in tool:
            result = self._step_chunking(context)
        elif "summarize_chunk" in tool:
            result = self._step_chunk_summarize(context)
        elif "merge_summaries" in tool:
            result = self._step_merge(context)
        elif "refine_summary" in tool:
            result = self._step_refine(context)
        elif "verify_claim" in tool:
            result = self._step_verify(context)
        elif "edit_summary" in tool or "edit" in tool:
            result = self._step_edit(context)
        elif "key_points" in tool or "outline" in tool:
            result = self._step_identify_key_points(context)
        else:
            # Fallback to keyword matching if tool is missing or unrecognized
            summarize_keywords = ["tóm tắt", "summar", "tóm lược"]
            if any(k in step_name for k in summarize_keywords):
                if any(k in step_name for k in ["chunk", "từng đoạn", "từng phần"]):
                    result = self._step_chunk_summarize(context)
                elif any(k in step_name for k in ["merge", "gộp", "kết hợp", "sáp nhập"]):
                    result = self._step_merge(context)
                elif any(k in step_name for k in ["refine", "tinh chỉnh", "hoàn thiện", "cải thiện", "refinement"]):
                    result = self._step_refine(context)
                else:
                    result = self._step_chunk_summarize(context)
            elif any(k in step_name for k in ["tách câu", "sentence", "split", "phân tách"]):
                result = self._step_split_sentences(context)
            elif any(k in step_name for k in ["chunk", "chia đoạn", "nhóm câu", "phân đoạn"]):
                result = self._step_chunking(context)
            elif any(k in step_name for k in ["verif", "kiểm chứng", "xác minh", "đối chiếu", "kiểm tra", "verification"]):
                result = self._step_verify(context)
            elif any(k in step_name for k in ["edit", "hiệu chỉnh", "phong cách", "chỉnh sửa", "biên tập"]):
                result = self._step_edit(context)
            elif any(k in step_name for k in ["xác định", "identify", "ý chính", "key point", "phân tích", "dàn ý", "outline"]):
                result = self._step_identify_key_points(context)
            else:
                result = self._step_generic(context)

        # --- Debug Logging ---
        debug.log_step(
            step_name=f"execution_agent.run.{step_id}",
            agent_name=self.name,
            phase="execution",
            input_summary=f"step_id={step_id}, step_name='{step.get('name', '')}'",
            output_data=result,
        )
        return result

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    @staticmethod
    def _get_retry_feedback_block(context: Dict[str, Any]) -> str:
        """Build a prompt block with feedback from previous retry, if any."""
        feedback = context.get("retry_feedback", "")
        if not feedback:
            return ""
        return f"""
### ⚠️ Phản hồi từ lần thử trước (BẮT BUỘC khắc phục)
{feedback}
Hãy đặc biệt chú ý sửa các vấn đề trên trong lần thử này.
"""

    def _step_split_sentences(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Split input text into sentences with IDs."""
        sentences = vn_tools.split_sentences(context["input_text"])
        return {
            "step_id": context["current_step"]["step_id"],
            "action": "split_sentences",
            "sentences": sentences,
            "sentence_count": len(sentences),
            "status": "completed",
        }

    def _step_chunking(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Group sentences into chunks."""
        sentences = context.get("sentences")
        if not sentences:
            sentences = vn_tools.split_sentences(context["input_text"])
        chunks = vn_tools.chunk_text(sentences)
        return {
            "step_id": context["current_step"]["step_id"],
            "action": "chunking",
            "chunks": chunks,
            "chunk_count": len(chunks),
            "status": "completed",
        }

    def _step_identify_key_points(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Identify key points and facts from the source text."""
        sentences = context.get("sentences")
        if not sentences:
            sentences = vn_tools.split_sentences(context["input_text"])

        sentences_text = "\n".join(
            f"[{s['sentence_id']}] {s['text']}" for s in sentences
        )

        prompt = f"""### Nhiệm vụ
Xác định các ý chính và fact quan trọng từ văn bản gốc bên dưới.

### Văn bản gốc (với sentence ID)
{sentences_text}

### Yêu cầu
1. Liệt kê các ý chính (key points) của văn bản
2. Với mỗi ý chính, ghi lại sentence_id nguồn
3. Đánh dấu các entity quan trọng (tên người, tổ chức, số liệu, địa điểm)

### Yêu cầu output
Trả về JSON:
```json
{{
  "key_points": [
    {{
      "point_id": 1,
      "content": "Nội dung ý chính",
      "source_sentence_ids": [1, 2],
      "entities": ["entity1", "entity2"],
      "importance": "high/medium/low"
    }}
  ],
  "total_key_points": <số ý chính>,
  "main_entities": ["entity quan trọng nhất"]
}}
```"""

        # Use agent model for analysis
        self.llm.load_agent_model()
        result = self._call_llm_json(prompt)
        result["step_id"] = context["current_step"]["step_id"]
        result["action"] = "identify_key_points"
        result["status"] = "completed"
        return result

    def _step_chunk_summarize(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize each chunk individually using the 3B summarizer model."""
        chunks = context.get("chunks")
        if not chunks:
            # Tự động khắc phục nếu Planner Agent quên xếp task 'chunking'
            sentences = context.get("sentences")
            if not sentences:
                sentences = vn_tools.split_sentences(context["input_text"])
            chunks = vn_tools.chunk_text(sentences)

        compression = vn_tools.compute_compression_target(
            vn_tools.count_words(context["input_text"])
        )
        words_per_chunk = max(
            30, compression["max_words"] // max(len(chunks), 1)
        )

        style_instruction = self._get_style_instruction(context["style"])

        # Switch to summarizer model
        self.llm.load_summarizer_model()

        chunk_summaries = []
        for chunk in chunks:
            criteria = self._get_professional_criteria_prompt(f"khoảng {words_per_chunk} từ")
            retry_block = self._get_retry_feedback_block(context)
            prompt = f"""{criteria}
{retry_block}
### Văn bản gốc cần tóm tắt (chunk {chunk['chunk_id']}):
{chunk['text']}

### Tóm tắt:"""

            summary_text = self._call_llm(prompt, max_tokens=512)
            chunk_summaries.append({
                "chunk_id": chunk["chunk_id"],
                "sentence_ids": chunk["sentence_ids"],
                "summary": summary_text.strip(),
                "word_count": vn_tools.count_words(summary_text),
            })

        return {
            "step_id": context["current_step"]["step_id"],
            "action": "chunk_summarize",
            "chunk_summaries": chunk_summaries,
            "total_chunks": len(chunk_summaries),
            "status": "completed",
        }

    def _step_merge(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Merge chunk summaries into a single draft summary."""
        chunk_summaries = context.get("chunk_summaries")
        if not chunk_summaries:
            return {
                "step_id": context["current_step"]["step_id"],
                "action": "merge",
                "status": "failed",
                "error": "No chunk summaries available.",
            }

        combined = "\n\n".join(
            f"[Chunk {cs['chunk_id']}] {cs['summary']}" for cs in chunk_summaries
        )

        compression = vn_tools.compute_compression_target(
            vn_tools.count_words(context["input_text"])
        )
        style_instruction = self._get_style_instruction(context["style"])

        # Use summarizer model for merging
        self.llm.load_summarizer_model()

        target_len = f"{compression['min_words']}\u2013{compression['max_words']} t\u1eeb"
        criteria = self._get_professional_criteria_prompt(target_len)
        retry_block = self._get_retry_feedback_block(context)
        
        prompt = f"""{criteria}
        
### Phong cách bổ sung
{style_instruction}
{retry_block}
### Các đoạn tóm tắt cần gộp
{combined}

### Bản tóm tắt gộp:"""

        merged = self._call_llm(prompt, max_tokens=768)

        return {
            "step_id": context["current_step"]["step_id"],
            "action": "merge",
            "merged_summary": merged.strip(),
            "word_count": vn_tools.count_words(merged),
            "status": "completed",
        }

    def _step_refine(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Globally refine the merged summary."""
        merged = context.get("merged_summary", "")
        if not merged:
            return {
                "step_id": context["current_step"]["step_id"],
                "action": "refine",
                "status": "failed",
                "error": "No merged summary available.",
            }

        compression = vn_tools.compute_compression_target(
            vn_tools.count_words(context["input_text"])
        )
        style_instruction = self._get_style_instruction(context["style"])

        # Use summarizer model
        self.llm.load_summarizer_model()

        target_len = f"{compression['min_words']}\u2013{compression['max_words']} t\u1eeb"
        criteria = self._get_professional_criteria_prompt(target_len)
        retry_block = self._get_retry_feedback_block(context)

        prompt = f"""{criteria}

### Phong cách bổ sung
{style_instruction}
{retry_block}
### Bản tóm tắt cần tinh chỉnh
{merged}

### Văn bản gốc (để tham khảo)
{self._truncate_text(context['input_text'], 2000)}

### Bản tóm tắt sau tinh chỉnh:"""

        refined = self._call_llm(prompt, max_tokens=768)

        return {
            "step_id": context["current_step"]["step_id"],
            "action": "refine",
            "refined_summary": refined.strip(),
            "word_count": vn_tools.count_words(refined),
            "status": "completed",
        }

    def _step_verify(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Verify claims in the summary against the source text."""
        summary = context.get("refined_summary") or context.get("merged_summary", "")
        if not summary:
            return {
                "step_id": context["current_step"]["step_id"],
                "action": "verify",
                "status": "failed",
                "error": "No summary available for verification.",
            }

        sentences = context.get("sentences")
        if not sentences:
            sentences = vn_tools.split_sentences(context["input_text"])

        sentences_text = "\n".join(
            f"[{s['sentence_id']}] {s['text']}" for s in sentences
        )

        # Use agent model for verification (reasoning task)
        self.llm.load_agent_model()

        prompt = f"""### Nhiệm vụ
Kiểm chứng từng mệnh đề (claim) trong bản tóm tắt bằng cách đối chiếu với văn bản gốc.

### Bản tóm tắt cần kiểm chứng
{summary}

### Văn bản gốc (với sentence ID)
{sentences_text}

### Quy tắc kiểm chứng
1. Tách bản tóm tắt thành các mệnh đề riêng biệt
2. Với mỗi mệnh đề, tìm câu nguồn (sentence_id) chứng minh
3. Đánh giá pass/fail:
   - pass: mệnh đề có bằng chứng trong văn bản gốc
   - fail: mệnh đề KHÔNG có trong văn bản gốc (hallucination)
4. Ghi confidence score (0.0 – 1.0)

### Yêu cầu output
Trả về JSON:
```json
{{
  "verification_report": [
    {{
      "claim_id": 1,
      "claim_text": "Nội dung mệnh đề",
      "status": "pass",
      "evidence": [
        {{
          "sentence_id": 3,
          "source_text": "Nội dung câu nguồn"
        }}
      ],
      "confidence": 0.95
    }}
  ],
  "overall_pass_rate": 1.0,
  "hallucination_detected": false
}}
```

Hãy chỉ trả về JSON."""

        result = self._call_llm_json(prompt, max_tokens=2048)
        result["step_id"] = context["current_step"]["step_id"]
        result["action"] = "verify"
        result["status"] = "completed"
        return result

    def _step_edit(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Final style editing pass."""
        summary = context.get("refined_summary") or context.get("merged_summary", "")
        if not summary:
            return {
                "step_id": context["current_step"]["step_id"],
                "action": "edit",
                "status": "failed",
                "error": "No summary available for editing.",
            }

        verification = context.get("verification_report") or []
        failed_claims = [
            v for v in verification
            if isinstance(v, dict) and v.get("status") == "fail"
        ]

        style_instruction = self._get_style_instruction(context["style"])

        compression = vn_tools.compute_compression_target(
            vn_tools.count_words(context["input_text"])
        )

        # Use summarizer model for editing
        self.llm.load_summarizer_model()

        target_len = f"{compression['min_words']}\u2013{compression['max_words']} t\u1eeb"
        criteria = self._get_professional_criteria_prompt(target_len)

        failed_block = ""
        if failed_claims:
            failed_str = json.dumps(failed_claims, ensure_ascii=False, indent=2)
            failed_block = f"""
### Mệnh đề bị FAIL (cần loại bỏ hoặc sửa)
{failed_str}
"""

        retry_block = self._get_retry_feedback_block(context)

        prompt = f"""{criteria}

### Phong cách bổ sung
{style_instruction}
{failed_block}
{retry_block}
### Bản tóm tắt cần hiệu chỉnh
{summary}

### Bản tóm tắt sau hiệu chỉnh:"""

        edited = self._call_llm(prompt, max_tokens=768)

        return {
            "step_id": context["current_step"]["step_id"],
            "action": "edit",
            "edited_summary": edited.strip(),
            "word_count": vn_tools.count_words(edited),
            "status": "completed",
        }

    def _step_generic(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle any unrecognized step by asking the LLM."""
        step = context["current_step"]

        # Use agent model
        self.llm.load_agent_model()

        prompt = f"""### Nhiệm vụ
Thực hiện bước sau trong quy trình tóm tắt văn bản:

### Thông tin bước
- Step ID: {step.get('step_id')}
- Tên: {step.get('name')}
- Mô tả: {step.get('description')}
- Output mong đợi: {step.get('expected_output')}

### Văn bản gốc
{self._truncate_text(context['input_text'], 2000)}

Hãy thực hiện bước này và trả về kết quả dưới dạng JSON."""

        result = self._call_llm_json(prompt)
        result["step_id"] = step.get("step_id")
        result["action"] = "generic"
        result["status"] = "completed"
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_professional_criteria_prompt(self, target_words: str) -> str:
        """Returns the centralized professional summarization criteria block."""
        return f"""Bạn là một hệ thống tóm tắt văn bản tiếng Việt chuyên nghiệp, có nhiệm vụ tạo ra bản tóm tắt chính xác, súc tích và có cấu trúc rõ ràng dựa trên các tiêu chí bắt buộc dưới đây.

        ===== MỤC TIÊU =====
        Tạo bản tóm tắt cho văn bản đầu vào sao cho:
        - Độ dài: {target_words}
        - Giữ lại đầy đủ nội dung cốt lõi
        - Loại bỏ thông tin dư thừa, ví dụ minh họa phụ, lặp ý

        ===== TIÊU CHÍ BẮT BUỘC =====
        1. ĐỘ CHÍNH XÁC (Accuracy)
        - Không được suy diễn.
        - Không thêm thông tin không có trong văn bản gốc.
        - Không thay đổi bản chất sự kiện, số liệu, mốc thời gian.
        2. BẢO TOÀN Ý CHÍNH (Content Coverage)
        Bắt buộc giữ lại:
        - Chủ đề trung tâm
        - Các luận điểm quan trọng
        - Kết luận hoặc thông điệp chính
        - Nếu có: số liệu, chính sách, quyết định quan trọng
        3. TÍNH CÔ ĐỌNG (Conciseness)
        - Loại bỏ chi tiết phụ, mô tả dài dòng
        - Không lặp lại ý tưởng dưới hình thức khác
        4. TÍNH MẠCH LẠC (Coherence)
        - Viết thành đoạn văn liền mạch
        - Ngôn ngữ học thuật, trung lập
        - Câu văn rõ ràng, logic
        5. XỬ LÝ NỘI DUNG NHẠY CẢM
        - Nếu văn bản có nội dung nhạy cảm, vẫn phải tóm tắt đầy đủ
        - Không được né tránh hoặc làm nhẹ nội dung

        ===== ĐỊNH DẠNG ĐẦU RA =====
        Chỉ xuất ra duy nhất phần tóm tắt.
        Không giải thích.
        Không bình luận.
        Không meta-text.
        Không mở đầu bằng “Dưới đây là bản tóm tắt…”.
        Không dùng bullet points."""

    @staticmethod
    def _get_style_instruction(style: str) -> str:
        if style == "news_brief":
            return (
                "Phong cách tin ngắn (news brief): câu ngắn, trực tiếp, "
                "khách quan, sử dụng thì quá khứ/hiện tại, "
                "đặt thông tin quan trọng nhất lên đầu (inverted pyramid)."
            )
        elif style == "academic_abstract":
            return (
                "Phong cách tóm tắt học thuật (academic abstract): "
                "câu hoàn chỉnh, trang trọng, khách quan, "
                "trình bày theo cấu trúc: bối cảnh → phương pháp → kết quả → kết luận."
            )
        return "Phong cách chung: rõ ràng, mạch lạc, khách quan."
