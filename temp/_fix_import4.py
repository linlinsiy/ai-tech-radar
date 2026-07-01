import re

path = r"D:\013148\code\AI技术趋势雷达\tech-research\internal\app\api\import_api.py"

with open(path, "rb") as f:
    raw = f.read()

if raw[:3] == b"\xef\xbb\xbf":
    raw = raw[3:]

# Clean: normalize line endings
text = raw.decode("utf-8")
text = text.replace("\r\n", "\n").replace("\r", "\n")
# Deduplicate blank lines (no more than 1 blank line in a row)
text = re.sub(r"\n{3,}", "\n\n", text)
text = text.strip() + "\n"

# Now fix: add session.commit() after KB upload section
# Pattern: except Exception as kbi:\n            logger.warning("KB upload init error"...)\n\n\n        result = {
old_pat = (
    'except Exception as kbi:\n'
    '            logger.warning("KB upload init error: %s", str(kbi))\n'
    '\n'
    '\n'
    '        result = {'
)
new_pat = (
    'except Exception as kbi:\n'
    '            logger.warning("KB upload init error: %s", str(kbi))\n'
    '\n'
    '        # 提交知识库映射记录（tags 在此持久化）\n'
    '        if kb_stats["success"] > 0:\n'
    '            session.commit()\n'
    '\n'
    '        result = {'
)

# Also fix any PowerShell corruption
text = text.replace(
    'if (kb_stats["success"] -gt 0) {\n            session.commit()\n        }',
    'if kb_stats["success"] > 0:\n            session.commit()'
)

if old_pat in text:
    text = text.replace(old_pat, new_pat)
    print("Applied session.commit() fix")
else:
    print("Pattern not found, checking alternative patterns")
    # Try alternative: first find the result line
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip() == "result = {":
            print(f"  result = {{ at line {i}, context:")
            for j in range(max(0, i-5), min(len(lines), i+2)):
                print(f"    {j}: {repr(lines[j])}")
            # Apply fix manually at this location
            lines.insert(i, "")
            lines.insert(i, "            session.commit()")
            lines.insert(i, "        if kb_stats[\"success\"] > 0:")
            lines.insert(i, "        # 提交知识库映射记录（tags 在此持久化）")
            text = "\n".join(lines)
            print("Applied fix at found location")
            break

# Remove any duplicate KB upload sections (keep only first)
kb_marker = 'kb_stats = {"attempted": 0, "success": 0, "failed": 0}'
first = text.find(kb_marker)
second = text.find(kb_marker, first + 1)
if second >= 0:
    # Find 'result = {' after the second occurrence
    result_pos = text.find("result = {", second)
    if result_pos >= 0:
        # Remove everything from second occurrence to just before result
        text = text[:second] + text[result_pos:]
        print("Removed duplicate KB section")

with open(path, "w", encoding="utf-8") as f:
    f.write(text)

import ast
try:
    ast.parse(text)
    print(f"Final lines: {text.count(chr(10))}, Syntax: OK")
except SyntaxError as e:
    print(f"Syntax error at line {e.lineno}: {e.msg}")
    lines = text.split("\n")
    if e.lineno and e.lineno <= len(lines):
        ctx_start = max(0, e.lineno - 3)
        for j in range(ctx_start, min(len(lines), e.lineno + 3)):
            prefix = ">>>" if j == e.lineno - 1 else "   "
            print(f"  {prefix} {j+1}: {lines[j][:120]}")
