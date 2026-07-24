@echo off
REM ============================================================================
REM 伏羲 Fuxi v1.44 - 看门狗脚本 (watchdog.bat)
REM ============================================================================
REM 功能:
REM   1. 检测 8080 (Fuxi-Main) 和 8000 (ChromaDB) 端口
REM   2. 服务不可达时自动重启
REM   3. 记录日志到 logs\watchdog.log
REM
REM 用法:
REM   手动运行:   scripts\watchdog.bat
REM   持续监控:   scripts\watchdog.bat --loop
REM   可在 NSSM 中将此脚本注册为服务实现持续监控
REM ============================================================================

setlocal enabledelayedexpansion

REM 配置
set "REPO_ROOT=%~dp0.."
set "LOG_FILE=%REPO_ROOT%\logs\watchdog.log"
set "MAIN_PORT=8080"
set "CHROMADB_PORT=8000"
set "CHECK_INTERVAL=30"
set "MAX_RETRIES=3"

REM 确保日志目录存在
if not exist "%REPO_ROOT%\logs" mkdir "%REPO_ROOT%\logs"

REM 参数解析
set "LOOP_MODE=0"
if "%1"=="--loop" set "LOOP_MODE=1"
if "%1"=="-l" set "LOOP_MODE=1"

REM ============================================================================
REM 辅助函数
REM ============================================================================

:log
    set "timestamp=%date% %time%"
    echo [%timestamp%] %~1 >> "%LOG_FILE%"
    echo [%timestamp%] %~1
    goto :eof

:check_port
    REM 参数: %1 = 端口号, %2 = 服务名称
    REM 使用 netstat 检测端口是否在监听
    netstat -an 2>nul | findstr ":%1 " | findstr "LISTENING" >nul 2>&1
    if !errorlevel! equ 0 (
        call :log "[OK] %~2 端口 %1 正在监听"
        exit /b 0
    ) else (
        call :log "[WARN] %~2 端口 %1 无响应"
        exit /b 1
    )
    goto :eof

:restart_service
    REM 参数: %1 = 服务名称 (NSSM 服务名)
    call :log "[ACTION] 尝试重启服务: %~1"
    
    REM 尝试通过 NSSM 重启
    nssm status "%~1" >nul 2>&1
    if !errorlevel! equ 0 (
        nssm restart "%~1" >nul 2>&1
        if !errorlevel! equ 0 (
            call :log "[OK] 通过 NSSM 重启 %~1 成功"
            exit /b 0
        )
    )
    
    REM NSSM 失败时，尝试直接启动
    if "%~1"=="Fuxi-Main" (
        call :log "[ACTION] NSSM 不可用，尝试直接启动 Fuxi-Main"
        start "伏羲-Fuxi-Main" /D "%REPO_ROOT%" python -u start_server.py
        call :log "[OK] 已直接启动 Fuxi-Main 进程"
    )
    
    if "%~1"=="Fuxi-ChromaDB" (
        call :log "[ACTION] NSSM 不可用，尝试直接启动 ChromaDB"
        start "伏羲-ChromaDB" /D "%REPO_ROOT%" chroma run --host localhost --port %CHROMADB_PORT% --path "%REPO_ROOT%\data\chromadb"
        call :log "[OK] 已直接启动 ChromaDB 进程"
    )
    
    exit /b 0
    goto :eof

:restart_fuxi_main
    call :log "[ACTION] 尝试重启伏羲 FastAPI 服务..."
    
    REM 方法1: 通过 NSSM
    nssm status "Fuxi-Main" >nul 2>&1
    if !errorlevel! equ 0 (
        nssm restart "Fuxi-Main" >nul 2>&1
        if !errorlevel! equ 0 (
            call :log "[OK] NSSM 重启 Fuxi-Main 成功"
            goto :eof
        )
    )
    
    REM 方法2: 通过 taskkill + 重启
    tasklist /fi "WINDOWTITLE eq 伏羲-Fuxi-Main" 2>nul | find "python" >nul
    if !errorlevel! equ 0 (
        call :log "[ACTION] 终止现有 Fuxi-Main 进程"
        taskkill /fi "WINDOWTITLE eq 伏羲-Fuxi-Main" /f >nul 2>&1
        timeout /t 3 /nobreak >nul
    )
    
    call :log "[ACTION] 直接启动 Fuxi-Main"
    start "伏羲-Fuxi-Main" /D "%REPO_ROOT%" python -u start_server.py
    call :log "[OK] Fuxi-Main 已通过 start 命令启动"
    goto :eof

:restart_chromadb
    call :log "[ACTION] 尝试重启 ChromaDB 服务..."
    
    REM 方法1: 通过 NSSM
    nssm status "Fuxi-ChromaDB" >nul 2>&1
    if !errorlevel! equ 0 (
        nssm restart "Fuxi-ChromaDB" >nul 2>&1
        if !errorlevel! equ 0 (
            call :log "[OK] NSSM 重启 ChromaDB 成功"
            goto :eof
        )
    )
    
    REM 方法2: 直接启动
    call :log "[ACTION] 直接启动 ChromaDB"
    start "伏羲-ChromaDB" /D "%REPO_ROOT%" chroma run --host localhost --port %CHROMADB_PORT% --path "%REPO_ROOT%\data\chromadb"
    call :log "[OK] ChromaDB 已通过 start 命令启动"
    goto :eof

REM ============================================================================
REM 主检查逻辑
REM ============================================================================

:main_check
    call :log "========== 看门狗检查开始 =========="

    REM 检查 ChromaDB (8000)
    call :check_port %CHROMADB_PORT% "ChromaDB"
    if !errorlevel! neq 0 (
        call :log "[ALERT] ChromaDB 端口 %CHROMADB_PORT% 不可达，尝试重启..."
        call :restart_chromadb
        REM 等待 ChromaDB 启动
        call :log "[WAIT] 等待 ChromaDB 启动 (15秒)..."
        timeout /t 15 /nobreak >nul
    )

    REM 检查 Fuxi Main (8080)
    call :check_port %MAIN_PORT% "Fuxi-Main"
    if !errorlevel! neq 0 (
        set retry_count=0
        :retry_loop
            set /a retry_count+=1
            call :log "[ALERT] Fuxi-Main 端口 %MAIN_PORT% 不可达 (重试 !retry_count!/%MAX_RETRIES%)"
            call :restart_fuxi_main
            
            REM 等待启动
            call :log "[WAIT] 等待 Fuxi-Main 启动 (20秒)..."
            timeout /t 20 /nobreak >nul
            
            REM 重新检查
            call :check_port %MAIN_PORT% "Fuxi-Main"
            if !errorlevel! equ 0 (
                call :log "[OK] Fuxi-Main 重启后恢复在线"
                goto :check_done
            )
            
            if !retry_count! lss %MAX_RETRIES% goto :retry_loop
        
        call :log "[CRITICAL] Fuxi-Main 在 %MAX_RETRIES% 次重启后仍不可达！需要人工干预！"
    )

    :check_done
    call :log "========== 看门狗检查结束 =========="
    call :log ""

    REM 如果不是循环模式，退出
    if "!LOOP_MODE!"=="0" goto :end

    REM 等待下一次检查
    timeout /t %CHECK_INTERVAL% /nobreak >nul
    goto :main_check

:end
    if "!LOOP_MODE!"=="1" goto :main_check
    endlocal
    exit /b 0
