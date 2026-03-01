
import sys
import os
from unittest.mock import MagicMock

# Giả lập lẫy các dependency để không phải load model thật
sys.modules['llama_cpp'] = MagicMock()
sys.modules['huggingface_hub'] = MagicMock()
sys.modules['config'] = MagicMock()

# Thêm path agents
sys.path.append(os.path.abspath('agents'))

try:
    from base_agent import BaseAgent
    
    class MockAgent(BaseAgent):
        def run(self, context):
            return {}

    agent = MockAgent("TestAgent", "Role")
    
    # Kiểm tra xem _call_llm có chấp nhận tham số 'stop' không
    # Chúng ta mock self.llm.generate để nó không làm gì
    agent.llm = MagicMock()
    
    print("Testing _call_llm with stop argument...")
    agent._call_llm("test prompt", stop=["stop_token"])
    print("SUCCESS: _call_llm accepted 'stop' argument.")
    
    print("Testing _call_llm_json (which uses stop internally)...")
    # Mock _call_llm để trả về chuỗi JSON hợp lệ
    agent._call_llm = MagicMock(return_value='{"key": "value"}')
    result = agent._call_llm_json("give me json")
    print(f"SUCCESS: _call_llm_json result: {result}")
    
    print("Verification complete.")
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)
