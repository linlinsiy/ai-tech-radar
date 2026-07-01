import json
with open(r"D:\013148\code\AI技术趋势雷达\tech-research\aws\data\interim\processed_hashes.json", "r", encoding="utf-8") as f:
    data = json.load(f)
print(f"Type: {type(data).__name__}, Entries: {len(data)}")
keys = list(data.keys())
print(f"First key: {keys[0]}")
entry = data[keys[0]]
print("Fields:", list(entry.keys()))
for k, v in entry.items():
    if isinstance(v, str) and len(v) > 80:
        print(f"  {k}: {v[:120]}...")
    else:
        print(f"  {k}: {repr(v)}")
# Also check if full_content exists
print("\nHas full_content:", "full_content" in entry)
print("Has raw_summary:", "raw_summary" in entry)
print("summary:", repr(entry.get("summary", "N/A")[:200]))
