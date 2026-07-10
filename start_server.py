import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uvicorn
from src.server import app

if __name__ == "__main__":
    print("Starting server on port 8080...")
    uvicorn.run(app, host="0.0.0.0", port=8080)