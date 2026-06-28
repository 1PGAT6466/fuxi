#!/usr/bin/env python3
import os
os.chdir('/home/feng-shaoxuan/kb-server')
with open('src/api/search.py') as f:
    c = f.read()
c = c.replace(
    'logger.exception("Exception in routers/search.py")',
    'import logging; logging.getLogger(__name__).exception("Exception in routers/search.py")'
)
with open('src/api/search.py','w') as f:
    f.write(c)
import py_compile
py_compile.compile('src/api/search.py', doraise=True)
print("FIXED")
