import_path = r"D:\013148\code\AI技术趋势雷达\tech-research\internal\app\api\import_api.py"
with open(import_path, "rb") as f:
    data = f.read()

# Find the exact call to generate_article_summary
idx = data.find(b"generate_article_summary(")
if idx >= 0:
    # Search for the 'category' line within the call
    cat_line = b"\n                            category="
    rel_idx = data.find(cat_line, idx)
    if rel_idx >= 0:
        insert_pos = rel_idx
        new_param = b",\n                            full_content=item.full_content or \"\""
        data = data[:insert_pos] + new_param + data[insert_pos:]
        with open(import_path, "wb") as f:
            f.write(data)
        print("import_api.py: added full_content param before category")
    else:
        print("category line not found near generate_article_summary")
        # Try broader search
        cat_idx = data.find(b"category=matched.category", idx)
        if cat_idx >= 0:
            # Find beginning of this line
            line_start = data.rfind(b"\n", 0, cat_idx)
            insert_pos = line_start
            new_param = b"\n                            full_content=item.full_content or \"\","
            data = data[:insert_pos] + new_param + data[insert_pos:]
            with open(import_path, "wb") as f:
                f.write(data)
            print("import_api.py: added full_content param (fallback)")
        else:
            print("Still not found")
else:
    print("generate_article_summary not found")
