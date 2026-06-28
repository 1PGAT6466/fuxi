# yggdrasil-server Dockerfile
# 知识库后端服务
FROM python:3.10-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY src/ ./src/
COPY frontend/ ./frontend/
COPY config/ ./config/

# 数据目录
RUN mkdir -p data logs uploads

EXPOSE 8080

ENV KB_HOST=0.0.0.0
ENV KB_PORT=8080
ENV DEEPSEEK_API_KEY=""

CMD ["python", "-m", "uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]
