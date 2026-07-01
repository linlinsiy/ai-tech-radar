path = r"D:\013148\code\AI技术趋势雷达\tech-research\internal\app\api\import_api.py"
with open(path, "rb") as f:
    data = f.read()

# Fix the broken lines using byte escape sequences
old = bytes([0x20]*28) + b'raw_summary=item.raw_summary or "",\r,\n' + bytes([0x20]*28) + b'full_content=item.full_content or ""\n' + bytes([0x20]*28) + b'category=matched.category if matched else None,'
new = bytes([0x20]*28) + b'raw_summary=item.raw_summary or "",\r\n' + bytes([0x20]*28) + b'full_content=item.full_content or "",\r\n' + bytes([0x20]*28) + b'category=matched.category if matched else None,'

if old in data:
    data = data.replace(old, new)
    with open(path, "wb") as f:
        f.write(data)
    print("Fixed!")
else:
    print("Byte pattern not found, checking...")
    idx = data.find(b"raw_summary=item.raw_summary")
    if idx >= 0:
        chunk = data[idx:idx+300]
        for i, b in enumerate(chunk):
            if b == 0x0d:
                print(f"  CR at offset {i}")
            elif b == 0x0a:
                print(f"  LF at offset {i}")
