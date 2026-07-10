import sys

# Read the file
with open('src/services/llm.py.9aa52af', 'rb') as f:
    data = f.read()

# Remove BOM if present
if data[:2] == b'\xff\xfe':
    data = data[2:]
    encoding = 'utf-16-le'
elif data[:2] == b'\xfe\xff':
    data = data[2:]
    encoding = 'utf-16-be'
else:
    encoding = 'utf-16'

content = data.decode(encoding)

# Replace smart quotes with regular quotes
content = content.replace('\u201c', '"').replace('\u201d', '"')
content = content.replace('\u2018', "'").replace('\u2019', "'")

# Write the fixed file
with open('src/services/llm.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('File fixed successfully')
