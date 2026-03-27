import os
import json
import pandas as pd
from dotenv import load_dotenv
from groq import Groq
from llm_loader import LLMManager

# Tải API keys (Groq)
load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")

if not groq_api_key:
    raise ValueError("❌ LỖI: Chưa có GROQ_API_KEY trong file .env.")

groq_client = Groq(api_key=groq_api_key)

# Cấu hình đường dẫn
EXCEL_FILE_PATH = "Thư mục KQ/VB gốc/variant B.xlsx"
OUTPUT_EXCEL_PATH = "Thư mục KQ/Data_Results/baseline_comparison.xlsx"
MULTI_AGENT_RESULTS_DIR = "Thư mục KQ/Data_Results"

def evaluate_with_groq(article, summary):
    """Sử dụng Groq LLM-as-a-Judge đánh giá điểm số 0.0 - 1.0"""
    prompt = f"""Bạn là một Chuyên gia đánh giá AI. Đánh giá bản tóm tắt bên dưới so với văn bản gốc.
Chấm điểm 0.0 (Tệ nhất) đến 1.0 (Hoàn hảo) cho 3 tiêu chí:
1. Faithfulness (Trung thực): Không bịa đặt, sai số liệu.
2. Relevance (Bao quát): Đủ ý chính, không sót thông điệp cốt lõi.
3. Coherence & Conciseness (Mạch lạc): Trôi chảy, logic, không rườm rà.

[VĂN BẢN GỐC]
{article}

[BẢN TÓM TẮT]
{summary}

Trả về định dạng JSON chính xác:
{{
  "faithfulness_score": 0.0, "faithfulness_reason": "",
  "relevance_score": 0.0, "relevance_reason": "",
  "coherence_conciseness_score": 0.0, "coherence_conciseness_reason": ""
}}"""
    try:
        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a JSON-generating evaluation AI. Output ONLY valid JSON matching the user's schema."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Lỗi Groq API: {e}")
        return None

def main():
    df = pd.read_excel(EXCEL_FILE_PATH).head(20)
    llm = LLMManager()

    results = []

    for index, row in df.iterrows():
        text_id = index + 1
        article = str(row.iloc[0])
        if len(article.strip()) < 10:
            continue
            
        print(f"\n--- Đang xử lý Text ID: {text_id} ---")

        # 1. Đọc kết quả của hệ thống Multi-Agent (chạy từ file abc.ipynb)
        agent_summary = "N/A"
        agent_file = os.path.join(MULTI_AGENT_RESULTS_DIR, f"text_{text_id}", "output.json")
        if os.path.exists(agent_file):
            with open(agent_file, "r", encoding="utf-8") as f:
                ag_data = json.load(f)
                agent_summary = ag_data.get("summary", "N/A")
        
        # 2. Sinh tóm tắt Baseline (Single-shot prompt)
        print("🤖 Đang gọi mô hình Baseline (Qwen 3B Single Prompt)...")
        llm.load_summarizer_model()
        baseline_prompt = f"Hãy tóm tắt ngắn gọn và chính xác văn bản sau đây:\n\n{article}\n\nTóm tắt:"
        baseline_summary = llm.generate(baseline_prompt, max_tokens=1024)
        llm.unload()
        
        # 3. Đánh giá bằng Groq (Baseline)
        print("⚖️ Đang gọi Groq Judge chấm điểm Baseline...")
        base_eval = evaluate_with_groq(article, baseline_summary)
        
        # 4. Đánh giá bằng Groq (Multi-Agent) nếu có
        print("⚖️ Đang gọi Groq Judge chấm điểm Multi-Agent...")
        agent_eval = evaluate_with_groq(article, agent_summary) if agent_summary != "N/A" else None
        
        result_row = {
            "ID": text_id,
            "Baseline_Summary": baseline_summary,
            "Agent_Summary": agent_summary,
            "Baseline_Faithfulness": base_eval.get("faithfulness_score") if base_eval else "N/A",
            "Agent_Faithfulness": agent_eval.get("faithfulness_score") if agent_eval else "N/A",
            "Baseline_Relevance": base_eval.get("relevance_score") if base_eval else "N/A",
            "Agent_Relevance": agent_eval.get("relevance_score") if agent_eval else "N/A",
            "Baseline_Coherence": base_eval.get("coherence_conciseness_score") if base_eval else "N/A",
            "Agent_Coherence": agent_eval.get("coherence_conciseness_score") if agent_eval else "N/A"
        }
        results.append(result_row)
        
        # Lưu file tạm sau mỗi bước
        pd.DataFrame(results).to_excel(OUTPUT_EXCEL_PATH, index=False)
        print(f"✅ Đã lưu so sánh ID {text_id}.")

    print("🎉 Hoàn tất đánh giá so sánh!")

if __name__ == "__main__":
    main()
