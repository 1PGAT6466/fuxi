@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
cd /d E:\fuxi-system\app

:: 获取本地 IP
set "LAN_IP="
for /f "delims=" %%i in ('python -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.connect(('8.8.8.8',80)); print(s.getsockname()[0]); s.close()" 2^>nul') do set "LAN_IP=%%i"

set "HNAME=%COMPUTERNAME%"

echo.
echo  ================================================
echo         伏羲 - 企业知识认知系统
echo  ================================================
echo  本地访问: http://localhost:8080
if defined LAN_IP echo  局域网:   http://!LAN_IP!:8080
echo  ================================================
echo.

start /MIN "C:\Users\Feng Shaoxuan\AppData\Local\Programs\Python\Python313\python.exe" -m uvicorn src.server:app --host 0.0.0.0 --port 8080

:: 等待服务启动
timeout /t 6 /nobreak >nul

echo.
echo  [伏羲] 服务已启动！
if defined LAN_IP echo  [伏羲] 其他电脑请访问: http://!LAN_IP!:8080
echo  [伏羲] 如果IP变了，重启此脚本会显示新地址
echo.