"""Fix garbled characters in llm.py"""
import re

path = 'src/services/llm.py'
with open(path, 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Fix garbled docstrings - replace non-printable chars in triple-quoted strings
# Pattern: find triple-quoted strings with non-printable characters
def fix_garbled(s):
    """Replace non-printable characters with readable text"""
    # Replace known garbled patterns
    replacements = {
        '\ue190': '',
        '\u936f': '',
        '\u20ac': '',
        '\u9488': '',
        '\u5924': '',
        '\u6493': '',
        '\u8f14': '',
        '\u92b9': '',
        '\u7ec7': '',
        '\u7528': '',
    }
    for old, new in replacements.items():
        s = s.replace(old, new)
    return s

# Fix specific known garbled docstrings
garbled_patterns = [
    ('"""鍏煎鏃ц皟鐢?"""', '"""兼容旧调用"""'),
    ('"""鍏煎鏃ц皟鐢?"""', '"""兼容旧调用"""'),
    ('"""鍏煎鏃ф祦寮忚皟鐢?"""', '"""兼容旧流式调用"""'),
]

for old, new in garbled_patterns:
    content = content.replace(old, new)

# Fix garbled Chinese in log messages
log_fixes = [
    ('MiMo API Key 鏈厤缃嗭紝璺宠繃 MiMo 鐩存帴灏濊瘯 DeepSeek',
     'MiMo API Key 未配置，跳过 MiMo 直接尝试 DeepSeek'),
    ('MiMo 澶辫触锛屽皾璇?DeepSeek',
     'MiMo 失败，尝试 DeepSeek'),
    ('DeepSeek 涔熷け璐?',
     'DeepSeek 也失败'),
    ('鍏煎鏃ф祦寮忚皟鐢?',
     '兼容旧流式调用'),
]

for old, new in log_fixes:
    if old in content:
        content = content.replace(old, new)
        print(f"Fixed: {old[:30]}...")

# Also clean any remaining non-printable characters in docstrings
# Find triple-quoted strings and clean them
import re

def clean_docstring(match):
    s = match.group(0)
    # Remove non-printable characters (keep ASCII + common CJK)
    cleaned = ''
    for c in s:
        if ord(c) < 128 or (0x4e00 <= ord(c) <= 0x9fff) or c in ' \n\r\t':
            cleaned += c
        else:
            cleaned += '?'  # Replace unknown chars
    return cleaned

# Apply to all triple-quoted strings
content = re.sub(r'"""[^"]*"""', clean_docstring, content, flags=re.DOTALL)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed garbled characters in llm.py")
