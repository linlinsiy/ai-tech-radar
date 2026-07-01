path = r'D:\013148\code\AI技术趋势雷达\tech-research\sql\ai_radar_ddl.sql'
with open(path, 'rb') as f:
    data = f.read()

# Add tags column after error_message in KbMapping section
old = b\"\"\"  error_message   TEXT                                    COMMENT '\u5165\u5e93\u5931\u8d25\u539f\u56e0',
  created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '\u521b\u5efa\u65f6\u95f4',\"\"\"
new = b\"\"\"  error_message   TEXT                                    COMMENT '\u5165\u5e93\u5931\u8d25\u539f\u56e0',
  tags            JSON            NULL                                COMMENT '\u6807\u7b7e\u952e\u503c\u5bf9',
  created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '\u521b\u5efa\u65f6\u95f4',\"\"\"

if old in data:
    data = data.replace(old, new)
    with open(path, 'wb') as f:
        f.write(data)
    print('DDL updated: tags column added to ai_radar_kb_mapping')
else:
    # Try alternative approach - find by ascii markers
    idx = data.find(b'ai_radar_kb_mapping')
    if idx >= 0:
        # Look for error_message line
        err_idx = data.find(b'error_message', idx)
        if err_idx >= 0:
            # Find end of that line
            ln_end = data.find(b'\n', err_idx)
            # Find next line with created_at
            ca_idx = data.find(b'created_at', ln_end)
            if ca_idx >= 0:
                insert_pos = data.find(b'\n', ca_idx - 20)  # go back to beginning of created_at line
                if insert_pos < 0:
                    insert_pos = ca_idx - 1
                tag_line = b\"\\n  tags            JSON            NULL                                COMMENT '\u6807\u7b7e\u952e\u503c\u5bf9',\"
                new_data = data[:insert_pos] + tag_line + data[insert_pos:]
                with open(path, 'wb') as f:
                    f.write(new_data)
                print('DDL updated (fallback method)')
            else:
                print('created_at not found after error_message')
        else:
            print('error_message not found in KbMapping section')
    else:
        print('ai_radar_kb_mapping not found')
