path = r"D:\013148\code\AI技术趋势雷达\tech-research\internal\app\api\import_api.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Line numbers (0-based): fix blocks are at 648-656 (with duplicates)
# Remove the duplicate block: lines 654-656 (0-based: 653-655)
# 653: blank
# 654: "# 提交知识库映射记录..."
# 655: "if kb_stats..."
# 656: "session.commit()"
# Keep the first fix block (lines 648-652)

# But first verify what's at those indices
for i in range(647, min(660, len(lines))):
    print(f"{i+1}: {lines[i].rstrip()}")

# The duplicate starts at line 653 (0-based), which has blank
# The actual duplicate fix is at 654-656 (0-based 653-655)
# We need to remove lines 653-656 (or 654-657) that form the duplicate block
# But also check if there are double blank lines we can clean

# Let me be precise: remove the second occurrence of the fix pattern
# Pattern to remove: lines with "# 提交知识库映射记录..."
found_first = False
to_remove = []
for i in range(640, min(660, len(lines))):
    if lines[i].strip() == "# 提交知识库映射记录（tags 在此持久化）":
        if not found_first:
            found_first = True
        else:
            # This is the duplicate - remove this line and next 2
            for j in range(i, i+4):
                if j < len(lines) and j not in to_remove:
                    to_remove.append(j)

if to_remove:
    for idx in sorted(to_remove, reverse=True):
        del lines[idx]
    print(f"Removed {len(to_remove)} duplicate lines")

with open(path, "w", encoding="utf-8") as f:
    f.writelines(lines)

import ast
ast.parse("".join(lines))
print(f"Final: {len(lines)} lines, Syntax OK")
