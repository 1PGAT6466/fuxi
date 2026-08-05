import uvicorn
import sys
import os

# 加载 .env 文件（必须在导入 src.config 之前）
from dotenv import load_dotenv
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print(f"Loaded .env from {dotenv_path}")
    print(f"KB_EMBEDDER_URL={os.getenv('KB_EMBEDDER_URL')}")

# 切换到 app 目录
app_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app")
os.chdir(app_dir)
sys.path.insert(0, app_dir)

if __name__ == "__main__":
    uvicorn.run("src.server:app", host="0.0.0.0", port=8080, workers=1)
