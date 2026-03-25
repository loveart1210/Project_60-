"""
Planner-Observation Agent – Analyzes a roadmap against the source text.

Input context keys:
  • roadmap    : dict (the current roadmap)
  • input_text : str  (original Vietnamese text – MUST be used to avoid hallucination)

Output:
  Observation report dict.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from agents.base_agent import BaseAgent


class PlannerObservationAgent(BaseAgent):

    def __init__(self) -> None:
        super().__init__(
            name="Planner-Observation Agent",
            role_description=(
                "Agent chuyên phân tích roadmap tóm tắt văn bản. "
                "Bạn phải đọc kỹ cả roadmap VÀ văn bản gốc để đánh giá "
                "roadmap đã bao quát đầy đủ nội dung chưa, có thiếu bước nào không, "
                "và các bước có phù hợp với văn bản gốc hay không."
            ),
        )

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        roadmap_str = json.dumps(context["roadmap"], ensure_ascii=False, indent=2)

        prompt = f"""### Nhiệm vụ
Phân tích roadmap tóm tắt bên dưới và đánh giá chất lượng so với văn bản gốc.

### Roadmap hiện tại
```json
{roadmap_str}
```

### Văn bản gốc
{self._truncate_text(context['input_text'])}

### Yêu cầu phân tích
Hãy phân tích roadmap theo các tiêu chí sau:
1. **Bao quát nội dung** (Coverage): Roadmap có bao phủ tất cả ý chính của văn bản gốc không?
2. **Tính cụ thể** (Specificity): Các bước có đủ chi tiết để thực thi không?
3. **Rủi ro hallucination**: Có bước nào có thể dẫn tới việc tạo fact không có trong nguồn không?
4. **Sử dụng tool**: Roadmap có tận dụng các tool có sẵn (word_tokenize, sent_tokenize, chunk_text) một cách hợp lý không?
5. **Thiếu sót**: Có bước quan trọng nào bị thiếu không?

### Yêu cầu output
Trả về JSON:
```json
{{
  "observation": {{
    "coverage_analysis": "Phân tích chi tiết...",
    "specificity_analysis": "Phân tích chi tiết...",
    "hallucination_risk_analysis": "Phân tích chi tiết...",
    "tool_utilization_analysis": "Phân tích chi tiết...",
    "missing_steps": ["bước thiếu 1", "bước thiếu 2"],
    "strengths": ["điểm mạnh 1", "điểm mạnh 2"],
    "weaknesses": ["điểm yếu 1", "điểm yếu 2"]
  }}
}}
```

Hãy chỉ trả về JSON, không giải thích thêm."""

        result = self._call_llm_json(prompt)

        # --- Debug Logging ---
        from debug_logger import DebugLogger
        debug = DebugLogger()
        debug.log_step(
            step_name="planner_observation_agent.run",
            agent_name=self.name,
            phase="planning",
            input_summary=f"roadmap_type={type(context.get('roadmap')).__name__}",
            output_data=result,
        )
        return result
