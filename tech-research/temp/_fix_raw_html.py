# -*- coding: utf-8 -*-
"""Fix RSS crawler and markdown generator."""
RSS_PATH = r"D:\013148\code\AI技术趋势雷达\tech-research\aws\app\crawler\rss_crawler.py"
MD_PATH = r"D:\013148\code\AI技术趋势雷达\tech-research\internal\app\kb\markdown_gen.py"

def fix_rss_crawler():
    with open(RSS_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    for i, line in enumerate(lines):
        new_lines.append(line)
        # Insert raw_html extraction after raw_summary line
        if 'raw_summary = entry.get("summary") or entry.get("description") or ""' in line:
            # check next few lines have author extraction comment
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                new_lines.append(lines[j])
                j += 1
                i = j - 1
            if j < len(lines) and "# " in lines[j] and any(ch in lines[j] for ch in ["\u63d0\u53d6\u4f5c\u8005", "\u4f5c\u8005"]):
                new_lines.append('''
                # 提取全文（RSS content:encoded 或 Atom content）
                raw_html = None
                if hasattr(entry, "content") and entry.content:
                    # feedparser 将 content:encoded 标准化为 entry.content 列表
                    raw_html = entry.content[0].get("value", "") or None
''')
        # Add raw_html to RawArticle constructor
        if 'raw_summary=raw_summary,' in line:
            new_lines.append('                    raw_html=raw_html,\n')

    with open(RSS_PATH, "w", encoding="utf-8", newline="") as f:
        f.writelines(new_lines)
    print("[OK] rss_crawler.py updated")

def fix_markdown_gen():
    with open(MD_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Update template: rename section, add raw_summary
    old = '## \u6458\u8981\n{summary_cn}\n"""'
    new = '## AI \u5206\u6790\u6458\u8981\n{summary_cn}\n\n## \u539f\u6587\u6458\u8981\n{raw_summary}\n"""'
    content = content.replace(old, new)

    # Add raw_summary param to function
    old_func = (
        'def generate_article_summary(\n'
        '    title: str,\n'
        '    source_name: str,\n'
        '    url: str,\n'
        '    summary_cn: str,\n'
        '    category: Optional[str] = None,\n'
        '    author: Optional[str] = None,\n'
        '    publish_time=None,\n'
        '    value_score: Optional[float] = None,\n'
        ') -> str:'
    )
    new_func = (
        'def generate_article_summary(\n'
        '    title: str,\n'
        '    source_name: str,\n'
        '    url: str,\n'
        '    summary_cn: str,\n'
        '    raw_summary: str = "",\n'
        '    category: Optional[str] = None,\n'
        '    author: Optional[str] = None,\n'
        '    publish_time=None,\n'
        '    value_score: Optional[float] = None,\n'
        ') -> str:'
    )
    content = content.replace(old_func, new_func)

    # Add raw_summary to format() call
    old_fmt = '        summary_cn=summary_cn,'
    new_fmt = '        summary_cn=summary_cn,\n        raw_summary=raw_summary or "N/A",'
    content = content.replace(old_fmt, new_fmt)

    with open(MD_PATH, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    print("[OK] markdown_gen.py updated")

if __name__ == "__main__":
    fix_rss_crawler()
    fix_markdown_gen()