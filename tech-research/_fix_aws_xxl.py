fpath = r'D:\013148\code\AI技术趋势雷达\tech-research\aws\app\jobs\xxl_executor.py'
with open(fpath, 'rb') as f:
    content = f.read().decode('utf-8')
marker = 'def create_xxl_runner(config) -> PyxxlRunner:'
idx = content.find(marker)
if idx < 0:
    marker = 'def create_xxl_runner(config):'
    idx = content.find(marker)
if idx < 0:
    print('ERROR: marker not found')
    exit(1)
prefix = content[:idx]
new_tail = open(r'D:\013148\code\AI技术趋势雷达\tech-research\_aws_xxl_tail.txt', 'r', encoding='utf-8').read()
new_content = prefix + new_tail
with open(fpath, 'wb') as f:
    f.write(new_content.encode('utf-8'))
print('OK')
