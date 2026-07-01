import os, sys

# Fix 1: l2_analysis.py
path = r'D:\013148\code\AI技术趋势雷达\tech-research\aws\app\processor\l2_analysis.py'
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace('model_name = self.prompts.render(', '_model_name = self.prompts.render(')
c = c.replace('model=model_name or "gpt-4o-mini"', 'model=self.config.l2_model["model"]')
with open(path, 'w', encoding='utf-8', newline='') as f:
    f.write(c)
print('l2_analysis.py OK')

# Fix 2: deep/insight.py
path2 = r'D:\013148\code\AI技术趋势雷达\tech-research\aws\app\deep\insight.py'
with open(path2, 'r', encoding='utf-8') as f:
    c2 = f.read()
c2 = c2.replace('model_name = self.prompts.render(', '_model_name = self.prompts.render(')
c2 = c2.replace('model=model_name or "gpt-4o"', 'model=self.config.l3_model["model"]')
with open(path2, 'w', encoding='utf-8', newline='') as f:
    f.write(c2)
print('insight.py OK')

# Fix 3: llm/client.py
path3 = r'D:\013148\code\AI技术趋势雷达\tech-research\aws\app\llm\client.py'
with open(path3, 'r', encoding='utf-8') as f:
    c3 = f.read()
old_u = 'usage = response.usage.model_dump() if response.usage else {}'
new_u = (
    'usage_raw = response.usage\n'
    '                if usage_raw is None:\n'
    '                    usage = {}\n'
    '                elif hasattr(usage_raw, ' + repr('model_dump') + '):\n'
    '                    usage = usage_raw.model_dump()\n'
    '                elif isinstance(usage_raw, dict):\n'
    '                    usage = usage_raw\n'
    '                else:\n'
    '                    usage = {"total_tokens": str(usage_raw)}'
)
c3 = c3.replace(old_u, new_u)
with open(path3, 'w', encoding='utf-8', newline='') as f:
    f.write(c3)
print('client.py OK')