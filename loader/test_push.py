import asyncio, sys
sys.path.insert(0, r'F:\公司知识平台\中宫--胃')
from stomach import digest_file
r = asyncio.run(digest_file(r'F:\公司知识平台\传入数据\原始文件\技术文档\(11)--系统参数设置.docx', push=True))
print(r)
