import sys, os

# Fix 1: llm/client.py - add JSON repair
path = r"D:\013148\code\AI技术趋势雷达\tech-research\aws\app\llm\client.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old = '            except json.JSONDecodeError as e:\n                logger.error("LLM \u54cd\u5e94\u975e JSON: %s", content[:200])\n                return None'
new = r'''            except json.JSONDecodeError:
                pass

            # Try to repair truncated JSON (LLM output may hit max_tokens)
            try:
                repaired = _repair_truncated_json(content)
                if repaired:
                    return json.loads(repaired)
            except json.JSONDecodeError:
                pass

            logger.error("LLM response not JSON: %s", content[:200])
            return None


def _repair_truncated_json(text):
    """
    Repair truncated JSON from LLM output.
    Counts unmatched braces/brackets and appends closing chars.
    Returns repaired JSON string or None.
    """
    brace_depth = 0
    bracket_depth = 0
    in_string = False
    escape_next = False

    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            brace_depth += 1
        elif ch == "}":
            brace_depth -= 1
        elif ch == "[":
            bracket_depth += 1
        elif ch == "]":
            bracket_depth -= 1

    if brace_depth == 0 and bracket_depth == 0 and not in_string:
        return None
    if brace_depth < 0 or bracket_depth < 0:
        return None

    repaired = text
    if in_string:
        repaired += '"'
    for _ in range(bracket_depth):
        repaired += "]"
    for _ in range(brace_depth):
        repaired += "}"

    return repaired
'''

if old in content:
    content = content.replace(old, new, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Fix 1 OK: llm/client.py")
else:
    print("Fix 1 FAIL: old pattern not found")
    sys.exit(1)
print("All fixes applied")
