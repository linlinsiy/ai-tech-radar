import pathlib, re
root = pathlib.Path(r"D:\013148\code")
d = [x for x in root.iterdir() if x.is_dir() and "技术趋势" in x.name][0]
f = list((d / "验证").glob("API*.md"))[0]
c = f.read_bytes()

# Find articles position
idx_articles = c.find(b'"articles"')
print(f"Articles at: {idx_articles}")

# Search for success response AFTER articles block
succ = bytes([0xe6, 0x88, 0x90, 0xe5, 0x8a, 0x9f, 0xe5, 0x93, 0x8d, 0xe5, 0xba, 0x94])
idx2 = c.find(succ, idx_articles)
print(f"Next success response after articles: {idx2}")

# Show everything from articles to that success response
print("=== Content from articles to success ===")
print(repr(c[idx_articles:idx2+30]))
print("=== End ===")
