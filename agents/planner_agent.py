"""
Planner Agent – Builds a summarization roadmap from the input text.

Input context keys:
  • input_text : str
  • word_count : int
  • style      : "news_brief" | "academic_abstract"
  • tools      : list of available tool descriptions
  • revision_instructions : str (optional – from Planner-Reflection)

Output:
  A roadmap dict with a list of ordered tasks.
"""

from __future__ import annotations

from typing import Any, Dict

from agents.base_agent import BaseAgent


class PlannerAgent(BaseAgent):

    def __init__(self) -> None:
        super().__init__(
            name="Planner Agent",
            role_description=(
                "Agent chuyên xây dựng roadmap (kế hoạch) cho nhiệm vụ tóm tắt văn bản tiếng Việt. "
                "Bạn phân tích input, xác định các ý chính cần giữ lại, và lên kế hoạch "
                "các bước thực hiện bao gồm: chunking, tóm tắt từng chunk, merge, refinement, "
                "verification, và hiệu chỉnh phong cách."
            ),
        )

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        revision = context.get("revision_instructions", "")
        revision_block = ""
        if revision:
            revision_block = (
                f"\n\n### Yêu cầu sửa đổi từ Reflection Agent:\n{revision}\n"
                "Hãy cập nhật roadmap theo các yêu cầu trên."
            )

        prompt = f"""### Nhiệm vụ
Xây dựng một roadmap chi tiết để tóm tắt văn bản tiếng Việt bên dưới.

### Thông tin đầu vào
- Độ dài văn bản: {context['word_count']} từ
- Phong cách tóm tắt: {context['style']}
- Ràng buộc output: 150–250 từ, không quá 20% độ dài input
- Chế độ: abstractive nhưng fact-grounded (cho phép diễn giải lại nhưng KHÔNG thay đổi entity)

### Các tool có sẵn
- word_tokenize: tách từ tiếng Việt (underthesea)
- sent_tokenize: tách câu tiếng Việt
- chunk_text: nhóm câu thành chunks
- summarize_chunk: tóm tắt một chunk bằng LLM
- merge_summaries: gộp nhiều bản tóm tắt lại thành một
- refine_summary: tinh chỉnh câu từ cho bản tóm tắt gộp
- verify_claim: kiểm chứng mệnh đề vs văn bản gốc
{revision_block}

### Văn bản gốc (trích đoạn)
{self._truncate_text(context['input_text'])}

### Yêu cầu output
Trả về JSON với cấu trúc:
```json
{{
  "roadmap": {{
    "tasks": [
      {{
        "step_id": "step_1",
        "name": "Tên bước",
        "description": "Mô tả chi tiết bước này",
        "tool": "tool sử dụng (nếu có)",
        "expected_output": "Mô tả output mong đợi"
      }}
    ],
    "total_steps": <số bước>,
    "notes": "Ghi chú thêm"
  }}
}}
```

Hãy chỉ trả về JSON, không giải thích thêm."""

        result = self._call_llm_json(prompt)

        # --- Debug Logging ---
        from debug_logger import DebugLogger
        debug = DebugLogger()
        debug.log_step(
            step_name="planner_agent.run",
            agent_name=self.name,
            phase="planning",
            input_summary=f"word_count={context.get('word_count')}, style={context.get('style')}",
            output_data=result,
        )
        return result
