import os

def fix_kb_client():
    path = r'D:\013148\code\AI技术趋势雷达\tech-research\internal\app\kb\kb_client.py'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix 1: _extract_file_id - handle non-dict objects that support .get()
    old_extract = '''    @staticmethod
    def _extract_file_id(result) -> Optional[str]:
        """\\u4ece upload_chunks \\u54cd\\u5e94\\u4e2d\\u63d0\\u53d6 file_id / document_id

        \\u5165\\u53c2\\uff1a
            result: SDK upload_chunks \\u8fd4\\u56de\\u7ed3\\u679c

        \\u51fa\\u53c2\\uff1a
            file_id \\u6216 document_id \\u5b57\\u7b26\\u4e32\\uff0c\\u65e0\\u6cd5\\u63d0\\u53d6\\u8fd4\\u56de None
        """
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            return (
                result.get("document_id")
                or result.get("file_id")
                or result.get("id")
                or result.get("data", {}).get("file_id")
                or result.get("data", {}).get("document_id")
            )
        return None'''

    new_extract = '''    @staticmethod
    def _extract_file_id(result) -> Optional[str]:
        """\\u4ece upload_chunks \\u54cd\\u5e94\\u4e2d\\u63d0\\u53d6 file_id / document_id

        \\u5165\\u53c2\\uff1a
            result: SDK upload_chunks \\u8fd4\\u56de\\u7ed3\\u679c\\uff08\\u53ef\\u80fd\\u662f dict \\u6216 SDK \\u81ea\\u5b9a\\u4e49\\u5bf9\\u8c61\\uff09

        \\u51fa\\u53c2\\uff1a
            file_id \\u6216 document_id \\u5b57\\u7b26\\u4e32\\uff0c\\u65e0\\u6cd5\\u63d0\\u53d6\\u8fd4\\u56de None
        """
        if isinstance(result, str):
            return result
        # 优先 try dict-like access（含 SDK \\u81ea\\u5b9a\\u4e49\\u5bf9\\u8c61\\u652f\\u6301 .get \\u4f46\\u4e0d\\u662f dict \\u7684\\u60c5\\u51b5\\uff09
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
        return None'''

    if old_extract in content:
        content = content.replace(old_extract, new_extract, 1)
        print('kb_client.py: FIXED _extract_file_id for non-dict SDK responses')
    else:
        # try a more lenient match
        print('kb_client.py: trying alternate match for _extract_file_id...')
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if '_extract_file_id' in line and 'def' in line:
                print(f'  found at line {i+1}: {line.strip()}')
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

fix_kb_client()
