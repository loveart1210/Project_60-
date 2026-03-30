"""
Execution-Reflection Agent – Evaluates observation and decides next action.

Input context keys:
  • observation      : dict (from Execution-Observation Agent)
  • current_step_idx : int  (index of the current step in roadmap)
  • total_steps      : int

Output:
  Decision dict:
    decision ∈ {"next_step", "retry", "finish"}
"""

from __future__ import annotations

import json
from typing import Any, Dict

from agents.base_agent import BaseAgent


class ExecutionReflectionAgent(BaseAgent):

    def __init__(self) -> None:
        super().__init__(
            name="Execution-Reflection Agent",
            role_description=(
                "Agent chuyên đánh giá kết quả thực thi và ra quyết định. "
                "Bạn nhìn vào phân tích của Observation Agent để chấm điểm "
                "và quyết định: đi đến bước tiếp theo (next_step), "
                "thử lại bước hiện tại (retry), hoặc kết thúc (finish)."
            ),
        )

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        obs_raw = json.dumps(context["observation"], ensure_ascii=False, indent=2)
        # Truncate to prevent context window overflow
        obs_str = self._truncate_text(obs_raw, 3000)

        prompt = f"""### Nhiệm vụ
Dựa trên phân tích của Execution-Observation Agent, hãy đánh giá và ra quyết định.

### Phân tích của Observation Agent
```json
{obs_str}
```

### Tiến trình
- Bước hiện tại: {context.get('current_step_idx', '?')} / {context.get('total_steps', '?')}
- Đây là bước cuối cùng: {"Có" if context.get('current_step_idx') == context.get('total_steps') else "Không"}

### Yêu cầu đánh giá
Chấm điểm kết quả thực thi (thang 0.0 – 1.0):
1. **Factual consistency**: Mức độ nhất quán với văn bản gốc
2. **Coverage completeness**: Mức độ bao quát
3. **Redundancy score**: Mức độ trùng lặp (0 = không trùng, 1 = rất trùng)
4. **Length compliance**: Đúng ràng buộc độ dài

### Quy tắc quyết định
- Nếu chất lượng tốt VÀ đây là bước cuối → "finish"
- Nếu chất lượng tốt (factual ≥ 0.8, coverage ≥ 0.7) → "next_step"
- Nếu có vấn đề nghiêm trọng (factual < 0.8 hoặc coverage < 0.7 hoặc có lỗi trong issues_found) → "retry". BẮT BUỘC phải điền thông tin vào "feedback". 

### Yêu cầu output
Trả về đúng định dạng JSON bên dưới (không bao gồm markdown ```json):
```json
{{
  "execution_reflection": {{
    "factual_consistency": 0.9,
    "coverage_completeness": 0.85,
    "redundancy_score": 0.1,
    "length_compliance": true,
    "decision": "next_step",
    "feedback": "[VÔ CÙNG QUAN TRỌNG] Tổng hợp chi tiết các lỗi từ 'issues_found' và 'quality_assessment'. Ghi rõ Execution Agent cần bổ sung gì, sửa gì. Tuyệt đối không copy lại câu mẫu này.",
    "reasoning": "Lý do quyết định dựa trên observation"
  }}
}}
```

Hãy chỉ trả về JSON."""

        result = self._call_llm_json(prompt)

        # --- Debug Logging ---
        from debug_logger import DebugLogger
        debug = DebugLogger()
        debug.log_step(
            step_name="execution_reflection_agent.run",
            agent_name=self.name,
            phase="execution",
            input_summary=f"step={context.get('current_step_idx')}/{context.get('total_steps')}",
            output_data=result,
        )
        return result
