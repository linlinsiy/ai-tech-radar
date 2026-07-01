import pathlib, re
root = pathlib.Path(r"D:\013148\code")
d = [x for x in root.iterdir() if x.is_dir() and "技术趋势" in x.name][0]
f = list((d / "验证").glob("API*.md"))[0]
c = f.read_bytes()

# Find the boundary: between current articles/analyses/insights block and "成功响应"
# The success response marker in bytes
success_bytes = bytes([0x2d, 0x20, 0x2a, 0x2a, 0xe6, 0x88, 0x90, 0xe5, 0x8a, 0x9f, 0xe5, 0x93, 0x8d, 0xe5, 0xba, 0x94, 0x2a, 0x2a])
idx_success = c.find(success_bytes)
print(f"Success response at: {idx_success}")

# Find articles start
idx_articles = c.find(b'"articles"')
print(f"Articles at: {idx_articles}")

# Show what's between
print("Between articles and success response:")
print(repr(c[idx_articles:idx_success+20]))

# Find the exact end of JSON
# Look for last "]\n  ]" or similar before success
end_search = c[:idx_success]
idx_json_end = end_search.rfind(b']\n  ]')
if idx_json_end < 0:
    idx_json_end = end_search.rfind(b']\n    ]')
if idx_json_end < 0:
    idx_json_end = end_search.rfind(b']\r\n  ]')
print(f"JSON end: {idx_json_end}")
print("Bytes near JSON end:", repr(c[idx_json_end-20:idx_json_end+30]))
