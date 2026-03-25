"""
Execution-Observation Agent – Analyzes output of an execution step.

Input context keys:
  • step_output : dict (output from the Execution Agent)
  • input_text  : str  (original Vietnamese text – for fact checking)
  • style       : str

Output:
  Observation report about the execution step quality.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from agents.base_agent import BaseAgent


class ExecutionObservationAgent(BaseAgent):

    def __init__(self) -> None:
        super().__init__(
            name="Execution-Observation Agent",
            role_description=(
                "Agent chuyên phân tích output của từng bước thực thi tóm tắt văn bản. "
                "Bạn phải đối chiếu output với văn bản gốc để đánh giá chất lượng, "
                "tính chính xác, và mức độ hoàn thành."
            ),
        )

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        step_output = context["step_output"]
        step_str = json.dumps(step_output, ensure_ascii=False, indent=2)

        prompt = f"""### Nhiệm vụ
Phân tích output của bước thực thi tóm tắt sau đây.

### Output của Execution Agent
```json
{self._truncate_text(step_str, 2500)}
```

### Văn bản gốc (để đối chiếu)
{self._truncate_text(context['input_text'], 2000)}

### Phong cách tóm tắt: {context['style']}

### Yêu cầu phân tích
1. **Tính chính xác** (Factual accuracy): Output có chứa fact không có trong văn bản gốc không?
2. **Mức độ hoàn thành**: Bước này đã hoàn thành đầy đủ chưa?
3. **Chất lượng**: Output có đạt chất lượng tốt không?
4. **Vấn đề phát hiện**: Có lỗi hoặc vấn đề gì không?

### Yêu cầu output
Trả về JSON:
```json
{{
  "execution_observation": {{
    "step_id": "{step_output.get('step_id', 'unknown')}",
    "action": "{step_output.get('action', 'unknown')}",
    "factual_accuracy": "Phân tích chi tiết...",
    "completion_status": "complete/incomplete",
    "quality_assessment": "Đánh giá chi tiết...",
    "issues_found": ["vấn đề 1", "vấn đề 2"],
    "summary": "Tóm tắt ngắn gọn kết quả phân tích"
  }}
}}
```

Hãy chỉ trả về JSON."""

        result = self._call_llm_json(prompt)

        # --- Debug Logging ---
        from debug_logger import DebugLogger
        debug = DebugLogger()
        debug.log_step(
            step_name="execution_observation_agent.run",
            agent_name=self.name,
            phase="execution",
            input_summary=f"step_id={step_output.get('step_id')}, action={step_output.get('action')}",
            output_data=result,
        )
        return result
