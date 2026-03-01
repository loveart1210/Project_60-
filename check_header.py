
import os

path = r"C:\Users\nguye\.cache\huggingface\hub\models--Qwen--Qwen2.5-7B-Instruct-GGUF\snapshots\bb5d59e06d9551d752d08b292a50eb208b07ab1f\qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf"

if os.path.exists(path):
    with open(path, "rb") as f:
        header = f.read(4)
        print(f"Header of shard 1: {header}")
        if header == b"GGUF":
            print("Magic number OK: 'GGUF'")
        else:
            print(f"INVALID Magic number: {header}")
else:
    print("File not found.")
