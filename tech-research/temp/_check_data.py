import json
with open(r"D:\013148\code\AI技术趋势雷达\tech-research\aws\data\interim\processed_hashes.json", "r", encoding="utf-8") as f:
    data = json.load(f)
print(f"Total records: {len(data)}")
print("Sample keys:", list(data[0].keys()) if data else "EMPTY")
# Check first entry for full_content
for k in data[0].keys():
    v = data[0][k]
    if isinstance(v, str) and len(v) > 50:
        print(f"  {k}: {v[:100]}...")
    else:
        print(f"  {k}: {repr(v)}")
