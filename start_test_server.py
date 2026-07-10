import sys
import os

# Set working directory to repo root
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Add repo root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment variables
os.environ["FUXI_ENV"] = "development"
os.environ["FUXI_JWT_SECRET"] = "test-secret-key-for-testing-only"

import uvicorn

if __name__ == "__main__":
    uvicorn.run("src.server:app", host="127.0.0.1", port=8080, log_level="info")
