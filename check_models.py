
import os
import sys

base_path = r"C:\Users\nguye\.cache\huggingface\hub\models--Qwen--Qwen2.5-7B-Instruct-GGUF\snapshots\bb5d59e06d9551d752d08b292a50eb208b07ab1f"

files_to_check = [
    "qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf",
    "qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf"
]

print(f"Checking path: {base_path}")
if not os.path.exists(base_path):
    print("Error: Snapshot directory does not exist.")
    sys.exit(1)

for f in files_to_check:
    full_path = os.path.join(base_path, f)
    if os.path.exists(full_path):
        size = os.path.getsize(full_path)
        print(f"Found: {f} | Size: {size} bytes ({size / (1024**3):.2f} GB)")
    else:
        print(f"MISSING: {f}")

# Check for other .gguf files in the same directory
print("\nOther GGUF files in directory:")
for entry in os.listdir(base_path):
    if entry.endswith(".gguf") and entry not in files_to_check:
        print(f" - {entry}")
