path = r"D:\013148\code\AI技术趋势雷达\tech-research\internal\app\api\import_api.py"

with open(path, "rb") as f:
    raw = f.read()

if raw[:3] == b"\xef\xbb\xbf":
    raw = raw[3:]

text = raw.decode("utf-8")
old_ps = "        if (kb_stats[\"success\"] -gt 0) {\n            session.commit()\n        }"
new_py = "        if kb_stats[\"success\"] > 0:\n            session.commit()"
if old_ps in text:
    text = text.replace(old_ps, new_py)
    print("PowerShell syntax -> Python syntax")

with open(path, "w", encoding="utf-8") as f:
    f.write(text)

import ast
ast.parse(open(path, encoding="utf-8").read())
print("Syntax check: OK")
