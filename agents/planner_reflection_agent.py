"""
Planner-Reflection Agent – Evaluates observation and decides next action.

Input context keys:
  • observation : dict (from Planner-Observation Agent)

Output:
  Decision dict with scores and action:
    decision ∈ {"finalize", "revise", "redo"}
"""

from __future__ import annotations

import json
from typing import Any, Dict

from agents.base_agent import BaseAgent


class PlannerReflectionAgent(BaseAgent):

    def __init__(self) -> None:
        super().__init__(
            name="Planner-Reflection Agent",
            role_description=(
                "Agent chuyên đánh giá và ra quyết định về roadmap tóm tắt văn bản. "
                "Bạn nhìn vào phân tích của Observation Agent để chấm điểm roadmap "
                "và quyết định: chốt roadmap (finalize), sửa đổi (revise), hoặc làm lại (redo)."
            ),
        )

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        obs_str = json.dumps(context["observation"], ensure_ascii=False, indent=2)

        prompt = f"""### Nhiệm vụ
Dựa trên phân tích của Observation Agent, hãy đánh giá roadmap và ra quyết định.

### Phân tích của Observation Agent
```json
{obs_str}
```

### Yêu cầu đánh giá
Chấm điểm roadmap theo từng tiêu chí (thang 0.0 – 1.0):
1. **Coverage Score**: Mức độ bao quát nội dung văn bản gốc
2. **Specificity Score**: Mức độ cụ thể và khả thi của các bước
3. **Hallucination Risk**: low / medium / high
4. **Tool Utilization**: adequate / inadequate

### Quy tắc quyết định
- Nếu coverage ≥ 0.8 VÀ specificity ≥ 0.7 VÀ hallucination risk = low → "finalize"
- Nếu có điểm yếu nhỏ cần sửa → "revise" + chỉ rõ cần sửa gì
- Nếu roadmap quá yếu (coverage < 0.5 hoặc hallucination risk = high) → "redo"

### Yêu cầu output
Trả về đúng định dạng JSON bên dưới (không bao gồm markdown ```json):
```json
{{
  "reflection": {{
    "coverage_score": 0.85,
    "specificity_score": 0.75,
    "hallucination_risk": "low",
    "tool_utilization": "adequate",
    "decision": "finalize",
    "revision_instructions": "Nếu decision là revise, ghi chi tiết hướng dẫn sửa. Nếu finalize thì để trống.",
    "reasoning": "Giải thích ngắn gọn lý do quyết định."
  }}
}}
```

Hãy chỉ trả về JSON, không giải thích thêm."""

        result = self._call_llm_json(prompt)
        return result
