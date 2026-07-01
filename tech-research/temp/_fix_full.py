import os,pathlib,re,hashlib,json
os.chdir(r'D:\013148\code')
dirs=[d for d in os.listdir('.') if os.path.isdir(d)]
target_dir=[d for d in dirs if d.startswith('AI')][0]
verify_dir=[d for d in os.listdir(target_dir) if d.startswith('\u9a8c')][0]
md_files=list(pathlib.Path(target_dir).glob(verify_dir+'/API*.md'))
p=md_files[0]
c=p.read_text(encoding='utf-8')

url='https://wechat2rss.bestblogs.dev/feed/e531a18b21c34cf787b83ab444eef659d7a980de.xml'
uh=hashlib.sha256(url.encode()).hexdigest()
fc='(\u5b8c\u6574\u539f\u6587\uff0c\u5b9e\u9645\u5b57\u6bb5\u8f83\u957f\uff0c\u6b64\u5904\u7701\u7565)'
ch=hashlib.sha256(fc.encode()).hexdigest()

# Replace <sha256hex> with real hash
c=c.replace('<sha256hex>', uh)

# Build articles block
article_block = '\n'.join([
    '  },',
    '  '+'"articles"'+': [',
    '    {',
    '     '+'"url"'+': '+'''+url+'"'+',',
    '     '+'"source_code"'+': '+'"'+'xin-zhi-yuan'+'"'+',',
    '      '+'"url_hash"'+': '+'"'+uh+'"'+',',
    '     '+'"title"'+': '+'"'+'GPT-5 掘糶性能突破：宎 MoE 到砆密架构的演逛'+'"'+',',
    '     '+'"author"'+': '+'"'+'John Doe'+'"'+',',
    '      '+'"publish_time"'+': '+'"'+'2026-06-15T10:00:00'+'"',',
    '     '+'"crawl_time"'+': '+'"'+'2026-06-16T08:00:00'+'"'+',',
    '      '+'"raw_summary"'+': '+'"'+'OpenAI 发布 GPT-5 技术报告, 撋露新一代模型在推理基准上的重大提升...'+'"'+',',
    '      '+'"full_content"'+': '+'"'+fc+'"'+',',
    '      '+'"content_hash"'+': '+'"'+ch+'"',
    '    }',
    '  ]',
])

# Replace the articles section
lines = c.split(\n')
s = None
for i, ln in enumerate(lines):
    if '"articles"' in ln and ':' in ln and '[' in ln:
        s = i
        break
e = None
for i in range(s+3, len(lines)):
    if lines[i].strip() == '}' and '[' not in lines[i+3]:
        e = i
        break

if s is None or e is None:
    print('NOT FOUND')
    exit(1)

lines[s:e+1] = [article_block]
c = '\n'.join(lines)

# Fix garbled text at success response
c = re.sub(r'\*\*[\ufffd]{5,7}\*\*', '**关攽不速**', c)

# Write back
p.write_text(c, encoding='utf-8')
print('SUCCESS')
