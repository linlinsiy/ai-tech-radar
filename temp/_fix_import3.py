path = r"D:\013148\code\AI技术趋势雷达\tech-research\internal\app\api\import_api.py"
with open(path, "rb") as f:
    raw = f.read()
if raw[:3] == b"\xef\xbb\xbf":
    raw = raw[3:]
text = raw.decode("utf-8")
lines = text.split("\n")
print(f"Total lines before: {len(lines)}")

# Remove duplicate KB upload section (lines 374-417, 0-based 373-416)
# Find the second occurrence of 'kb_stats = {' which starts the duplicate
first_kb = None
second_kb = None
for i, line in enumerate(lines):
    if line.strip() == 'kb_stats = {"attempted": 0, "success": 0, "failed": 0}':
        if first_kb is None:
            first_kb = i
        elif second_kb is None:
            second_kb = i

if second_kb:
    # Find the end of the duplicate section (where result = { starts)
    result_idx = None
    for i in range(second_kb, len(lines)):
        if lines[i].strip() == "result = {":
            result_idx = i
            break
    if result_idx:
        print(f"Removing duplicate KB section: lines {second_kb}-{result_idx-1}")
        del lines[second_kb:result_idx]

# Fix PowerShell syntax: change 'if (kb_stats["success"] -gt 0) {' to Python
for i, line in enumerate(lines):
    if '-gt 0)' in line and 'kb_stats' in line:
        print(f"Fixing PowerShell syntax at line {i}")
        lines[i] = '        if kb_stats["success"] > 0:'
        # Remove the closing brace on next line if present
        if i+1 < len(lines) and lines[i+1].strip() == '}':
            del lines[i+1]
        break

# Write back
result = "\n".join(lines)
with open(path, "w", encoding="utf-8") as f:
    f.write(result)

import ast
try:
    ast.parse(result)
    print(f"Total lines after: {result.count(chr(10))}")
    print("Syntax check: OK")
except SyntaxError as e:
    print(f"Syntax error at line {e.lineno}: {e.msg}")
    # Show the offending line
    rlines = result.split("\n")
    if e.lineno and e.lineno <= len(rlines):
        print(f"  Content: {rlines[e.lineno-1][:120]}")
