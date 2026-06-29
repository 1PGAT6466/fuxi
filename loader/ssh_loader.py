import pexpect
import sys

host = "172.25.30.16"
user = "feng-shaoxuan"
password = "pgat.2026"
cmd = "hostname & dir F:\\公司知识平台 /b"

p = pexpect.spawn(f"ssh -o StrictHostKeyChecking=no {user}@{host} {cmd}", timeout=15, encoding='utf-8')
idx = p.expect(["password:", "yes/no", pexpect.EOF, pexpect.TIMEOUT], timeout=10)
if idx == 0:
    p.sendline(password)
elif idx == 1:
    p.sendline("yes")
    p.expect("password:")
    p.sendline(password)

p.expect(pexpect.EOF, timeout=10)
print(p.before)
p.close()
