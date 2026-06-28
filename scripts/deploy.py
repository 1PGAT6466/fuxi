"""
kb-server 部署脚本
在 kb-server (172.25.30.200) 上运行:
  python deploy.py [--restart]
"""
import subprocess
import sys
from pathlib import Path

SERVER_DIR = Path("/home/feng-shaoxuan/kb-server")
SRC_DIR = SERVER_DIR / "src"
GIT_REMOTE = "origin"  # TODO: 替换为 GitHub URL

def git_pull():
    print("Pulling latest from GitHub...")
    result = subprocess.run(
        ["git", "-C", str(SERVER_DIR), "pull", GIT_REMOTE, "main"],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"Git pull failed: {result.stderr}")
        return False
    return True

def restart_server():
    print("Restarting kb-server...")
    # 假设使用 systemd
    subprocess.run(["sudo", "systemctl", "restart", "kb-server"])
    subprocess.run(["sudo", "systemctl", "status", "kb-server", "--no-pager"])

if __name__ == "__main__":
    if "--restart" in sys.argv:
        restart_server()
    else:
        if git_pull():
            restart_server()
