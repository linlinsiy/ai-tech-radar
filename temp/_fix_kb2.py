# Fix kb_client.py _extract_file_id to handle non-dict responses
path = r'D:\013148\code\AI技术趋势雷达\tech-research\internal\app\kb\kb_client.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the _extract_file_id method (starts around line 155)
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    if '@staticmethod' in line and i+1 < len(lines) and '_extract_file_id' in lines[i+1]:
        # This is the start of _extract_file_id
        new_lines.append(line)  # @staticmethod
        new_lines.append(lines[i+1])  # def _extract_file_id
        new_lines.append(lines[i+2])  # docstring start
        new_lines.append(lines[i+3])  # docstring cont
        new_lines.append(lines[i+4])  # docstring cont
        new_lines.append(lines[i+5])  # docstring cont
        new_lines.append(lines[i+6])  # docstring cont
        new_lines.append(lines[i+7])  # docstring end
        
        # Replace the method body (starting from line i+8: "if isinstance(result, str):" until we hit another def or end of class)
        j = i + 8
        while j < len(lines):
            stripped = lines[j].strip()
            if stripped.startswith('def ') or stripped.startswith('@') or (stripped == '' and j > i+15 and j+1 < len(lines) and (lines[j+1].strip().startswith('def ') or lines[j+1].strip().startswith('#'))):
                break
            j += 1
        
        # Insert new method body
        new_lines.append('''        """\\u4ece upload_chunks \\u54cd\\u5e94\\u4e2d\\u63d0\\u53d6 file_id / document_id

        \\u5165\\u53c2\\uff1a
            result: SDK upload_chunks \\u8fd4\\u56de\\u7ed3\\u679c\\uff08\\u53ef\\u80fd\\u662f dict \\u6216 SDK \\u81ea\\u5b9a\\u4e49\\u5bf9\\u8c61\\uff09

        \\u51fa\\u53c2\\uff1a
            file_id \\u6216 document_id \\u5b57\\u7b26\\u4e32\\uff0c\\u65e0\\u6cd5\\u63d0\\u53d6\\u8fd4\\u56de None
        """
        if isinstance(result, str):
            return result
        # \\u4f18\\u5148 try dict-like access\\uff08\\u542b SDK \\u81ea\\u5b9a\\u4e49\\u5bf9\\u8c61\\u652f\\u6301 .get \\u4f46\\u4e0d\\u662f dict \\u7684\\u60c5\\u51b5\\uff09
        try:
            doc_id = result.get("document_id")
            if doc_id:
                return doc_id
            file_id = result.get("file_id")
            if file_id:
                return file_id
            obj_id = result.get("id")
            if obj_id:
                return obj_id
            data = result.get("data")
            if isinstance(data, dict):
                return data.get("file_id") or data.get("document_id")
        except (AttributeError, TypeError):
            pass
        # \\u5c1d\\u8bd5\\u901a\\u8fc7 dict() \\u8f6c\\u6362 SDK \\u5bf9\\u8c61
        try:
            d = dict(result)
            return d.get("document_id") or d.get("file_id") or d.get("id")
        except (ValueError, TypeError):
            pass
        return None
''')
        i = j
    else:
        new_lines.append(line)
        i += 1

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print('kb_client.py: FIXED - _extract_file_id handles non-dict SDK responses')
