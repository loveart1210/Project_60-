import os
from dotenv import load_dotenv
from llm_loader import LLMManager

# Ưu tiên load thông số chia tải VRAM và các cấu hình khác từ file .env
load_dotenv()

def test_ai():
    print("1. Đang khởi tạo hệ thống quản lý AI...")
    manager = LLMManager()

    print("\n2. Đang tải mô hình Summarizer (3B) và chia tải VRAM...")
    print("=> Hãy mở Task Manager (Ctrl + Shift + Esc) -> Tab Performance.")
    print("=> Quan sát xem VRAM của GPU RTX 3050 có tăng lên không, và RAM hệ thống tăng bao nhiêu.")
    
    # Hàm này sẽ tự động đọc cấu hình trong config.py (đã được móc nối với .env của bạn)
    manager.load_summarizer_model()
    
    print("\n3. Tải thành công! Đang thử sinh chữ...")
    prompt = "Xin chào, hãy đếm từ 1 đến 5."
    
    # Chạy thử model
    response = manager.generate(prompt, max_tokens=50)
    print("\n[AI Trả lời]:", response)

    print("\n4. Đang dọn dẹp VRAM...")
    manager.unload()
    print("Hoàn tất test!")

if __name__ == "__main__":
    test_ai()