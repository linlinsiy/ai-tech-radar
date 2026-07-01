import re

models_path = r'D:\013148\code\AI技术趋势雷达\tech-research\internal\app\db\models.py'
with open(models_path, 'rb') as f:
    data = f.read()

# Pattern: error_message line ending with )\r\n\r\n\r\ndef get_engine
old = b'error_message = Column(Text, comment='
# Find the full line
idx = data.find(old)
if idx >= 0:
    line_end = data.find(b'\r\n', idx)
    error_line = data[idx:line_end]
    rest = data[line_end:]
    
    # New lines to insert
    new_cols = b'\r\n    tags = Column(JSON, comment="\xe6\xa0\x87\xe7\xad\xbe\xe9\x94\xae\xe5\x80\xbc\xe5\xaf\xb9")\r\n    created_at = Column(DateTime, default=datetime.now, comment="\xe5\x88\x9b\xe5\xbb\xba\xe6\x97\xb6\xe9\x97\xb4")\r\n    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="\xe6\x9b\xb4\xe6\x96\xb0\xe6\x97\xb6\xe9\x97\xb4")'
    
    new_data = data[:line_end] + new_cols + rest
    
    # Backup
    import shutil
    shutil.copy(models_path, models_path + '.bak')
    
    with open(models_path, 'wb') as f:
        f.write(new_data)
    print('KbMapping model updated successfully')
else:
    print('Pattern not found')
