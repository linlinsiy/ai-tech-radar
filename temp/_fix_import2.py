import sys

path = r"D:\013148\code\AI技术趋势雷达\tech-research\internal\app\api\import_api.py"

# Read current file
with open(path, "rb") as f:
    raw = f.read()

# Remove BOM
if raw[:3] == b"\xef\xbb\xbf":
    raw = raw[3:]

text = raw.decode("utf-8")
lines = text.split("\n")

# The issue: PowerShell inserted lines 369-372 (PowerShell syntax), and lines 374+ duplicate the KB upload section
# Target: Replace the PowerShell syntax line with Python syntax, remove duplicate KB section
# Line 369: '        # 提交知识库映射记录（tags 在此持久化）'
# Line 370: '        if (kb_stats["success"] -gt 0) {'
# Line 371: '            session.commit()'
# Line 372: '        }'

# Find the correct insertion point: before "        result = {"
result_idx = None
for i, line in enumerate(lines):
    if line.strip() == "result = {":
        result_idx = i
        break

if result_idx:
    print(f"'result = {{' found at line {result_idx}")
    # Find the PowerShell syntax block before result
    for j in range(result_idx - 10, result_idx):
        if "kb_stats" in lines[j] and "-gt" in lines[j]:
            print(f"PowerShell syntax at line {j}: {lines[j]}")
            # Replace with Python syntax
            lines[j] = '        if kb_stats["success"] > 0:'
            lines[j+1] = '            session.commit()'
            # Remove '        }' line
            del lines[j+2]
            print("Replaced PowerShell -> Python")
            break
else:
    print("result = { not found, searching for pattern...")
    for i, line in enumerate(lines):
        if "result" in line and "batch_no" in line:
            print(f"  Line {i}: {repr(line)}")

# Write result
with open(path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

# Verify syntax
import ast
try:
    ast.parse(open(path, encoding="utf-8").read())
    print("Syntax check: OK")
except SyntaxError as e:
    print(f"Syntax error: {e}")
