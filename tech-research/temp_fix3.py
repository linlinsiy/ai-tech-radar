import sys

# Fix 3: collect_job.py
# Remove duplicate content_hash loop and add URL fallback
path = r"D:\013148\code\AI技术趋势雷达\tech-research\aws\app\jobs\collect_job.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# The anchor appears twice (duplicate loop). Replace the SECOND occurrence block.
# Strategy: replace the duplicated block with empty, then add fallback to the first.
anchor = 'hash_source = (hash_source + "\\n" + art.raw_html)[:8000]'
pos1 = content.find(anchor)
pos2 = content.find(anchor, pos1 + 1)
print(f"First anchor at {pos1}, Second at {pos2}")

if pos2 > pos1:
    # Remove the duplicate loop block (from "# for all articles" or similar through the second anchor's whole block)
    # Find the start of the duplicate block
    # The block starts with garbled comment line before "for r in l2_results:"
    block_start = content.rfind("for r in l2_results:", 0, pos2)
    # Find end of block (after the second compute_content_hash)
    block_end = content.find("\n\n", pos2)
    if block_end < 0:
        block_end = len(content)
    else:
        block_end += 2  # include the blank line

    print(f"Block to remove: {block_start}-{block_end}")
    old_block = content[block_start:block_end]
    # Replace with empty (remove the duplicate)
    content = content.replace(old_block, "", 1)
    print("Duplicate loop removed")

    # Now add URL fallback to the first loop
    # The first loop has: if hash_source: art.compute_content_hash(hash_source)
    old_first = '                if hash_source:\n                    art.compute_content_hash(hash_source)'
    new_first = '                if not hash_source:\n                    hash_source = art.url or ""\n                if hash_source:\n                    art.compute_content_hash(hash_source)'
    if old_first in content:
        content = content.replace(old_first, new_first, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("Fix 3 OK: jobs/collect_job.py")
    else:
        print("Fix 3 FAIL: first loop pattern not found after removal")
else:
    print("Fix 3 FAIL: second anchor not found")
