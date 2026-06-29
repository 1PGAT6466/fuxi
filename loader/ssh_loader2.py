#!/usr/bin/env python3
"""SSH to loader 172.25.30.16 with password"""
import pexpect, sys

p = pexpect.spawn(
    "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 feng-shaoxuan@172.25.30.16 \"hostname & dir F:\\公司知识平台 /b\"",
    timeout=20,
    encoding="utf-8",
)
p.logfile_read = sys.stdout

idx = p.expect(["password:", "yes/no", "Permission denied", pexpect.EOF], timeout=15)
print(f"\n--- MATCH: {idx} ---")
if idx == 0:
    p.sendline("pgat.2026")
    p.expect(pexpect.EOF, timeout=15)
elif idx == 1:
    p.sendline("yes")
    idx2 = p.expect(["password:", pexpect.EOF], timeout=10)
    if idx2 == 0:
        p.sendline("pgat.2026")
        p.expect(pexpect.EOF, timeout=15)

print(f"\nEXIT: {p.exitstatus}")
p.close()
