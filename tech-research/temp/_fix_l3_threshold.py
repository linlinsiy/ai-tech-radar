# fix_threshold.py
import os
base = r"D:\013148\code\AI技术趋势雷达\tech-research\aws"

# 1. config.properties
fp = os.path.join(base, "config", "config.properties")
with open(fp, "r", encoding="utf-8") as f:
    c = f.read()
c = c.replace("deep_insight.min_value_score=8.0", "deep_insight.min_value_score=7.0")
with open(fp, "w", encoding="utf-8", newline="") as f:
    f.write(c)
print("[OK] config.properties")

# 2. config.py default
fp = os.path.join(base, "app", "config.py")
with open(fp, "r", encoding="utf-8") as f:
    c = f.read()
old = '"deep_insight.min_value_score", 8.0'
new = '"deep_insight.min_value_score", 7.0'
c = c.replace(old, new)
with open(fp, "w", encoding="utf-8", newline="") as f:
    f.write(c)
print("[OK] config.py")

# 3. insight.py default
fp = os.path.join(base, "app", "deep", "insight.py")
with open(fp, "r", encoding="utf-8") as f:
    c = f.read()
c = c.replace("min_score: float = 8.0", "min_score: float = 7.0")
with open(fp, "w", encoding="utf-8", newline="") as f:
    f.write(c)
print("[OK] insight.py")
print("All done: 8.0 -> 7.0")
