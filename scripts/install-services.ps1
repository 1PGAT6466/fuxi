# ============================================================================
# 伏羲 Fuxi v1.44 - NSSM 进程守护安装脚本
# ============================================================================
# 功能:
#   1. 安装 NSSM (Non-Sucking Service Manager)
#   2. 注册 ChromaDB 服务 (Fuxi-ChromaDB)
#   3. 注册 FastAPI 服务 (Fuxi-Main)
#   4. 配置自动恢复 (崩溃后 5 秒重启)
#   5. 配置日志输出
#
# 用法:
#   安装所有服务:        powershell -File scripts\install-services.ps1
#   预览模式 (不执行):   powershell -File scripts\install-services.ps1 -WhatIf
#   仅安装 ChromaDB:     powershell -File scripts\install-services.ps1 -Service ChromaDB
#   仅安装 FastAPI:      powershell -File scripts\install-services.ps1 -Service Main
#   卸载所有服务:        powershell -File scripts\install-services.ps1 -Uninstall
# ============================================================================

param(
    [switch]$WhatIf,
    [switch]$Uninstall,
    [ValidateSet("ChromaDB", "Main", "All")]
    [string]$Service = "All"
)

# 脚本需要管理员权限
$ErrorActionPreference = "Stop"

# 路径配置
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$DataDir = Join-Path $RepoRoot "data"
$LogsDir = Join-Path $RepoRoot "logs"
$NssmDir = Join-Path $RepoRoot "tools\nssm"
$NssmExe = Join-Path $NssmDir "nssm.exe"

# NSSM 下载 URL (预编译版本)
$NssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
$NssmZip = Join-Path $env:TEMP "nssm-2.24.zip"

# ChromaDB 配置
$ChromaServiceName = "Fuxi-ChromaDB"
$ChromaHost = "localhost"
$ChromaPort = 8000
$ChromaDataDir = Join-Path $DataDir "chromadb"

# FastAPI (伏羲 Main) 配置
$MainServiceName = "Fuxi-Main"
$MainHost = "0.0.0.0"
$MainPort = 8080
$MainWorkingDir = $RepoRoot

# ============================================================================
# 辅助函数
# ============================================================================

function Write-Step {
    param([string]$Message, [string]$Status = "")
    $timestamp = Get-Date -Format "HH:mm:ss"
    if ($Status) {
        Write-Host "[$timestamp] $Message ... $Status" -ForegroundColor Cyan
    } else {
        Write-Host "[$timestamp] $Message" -ForegroundColor Cyan
    }
}

function Write-Success {
    param([string]$Message)
    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host "[$timestamp]   [OK] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host "[$timestamp] [WARN] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host "[$timestamp] [ERROR] $Message" -ForegroundColor Red
}

function Test-Admin {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Error "此脚本需要管理员权限运行！请以管理员身份打开 PowerShell 后重试。"
        Write-Host ""
        Write-Host "右键点击 PowerShell 图标 → 以管理员身份运行" -ForegroundColor Yellow
        Write-Host ""
        exit 1
    }
}

function Install-Nssm {
    # 检查 NSSM 是否已在 PATH 中
    $nssmInPath = Get-Command nssm.exe -ErrorAction SilentlyContinue
    if ($nssmInPath) {
        Write-Success "NSSM 已在 PATH 中: $($nssmInPath.Source)"
        $script:NssmExe = $nssmInPath.Source
        return $true
    }

    # 检查本地 tools 目录
    if (Test-Path $NssmExe) {
        Write-Success "NSSM 已存在于工具目录: $NssmExe"
        return $true
    }

    Write-Step "NSSM 未安装，开始下载..." "DOWNLOADING"

    if ($WhatIf) {
        Write-Warning "[WhatIf] 将下载 NSSM 到 $NssmDir"
        return $true
    }

    try {
        # 创建工具目录
        if (-not (Test-Path $NssmDir)) {
            New-Item -ItemType Directory -Path $NssmDir -Force | Out-Null
        }

        # 下载 NSSM
        Write-Step "下载 NSSM 2.24..." "DOWNLOADING"
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $NssmUrl -OutFile $NssmZip

        # 解压
        Write-Step "解压 NSSM..." "EXTRACTING"
        Expand-Archive -Path $NssmZip -DestinationPath $NssmDir -Force
        Remove-Item $NssmZip -Force

        # 查找 nssm.exe (可能在子目录中)
        $extractedNssm = Get-ChildItem -Path $NssmDir -Recurse -Filter "nssm.exe" | Select-Object -First 1
        if ($extractedNssm) {
            if ($extractedNssm.DirectoryName -ne $NssmDir) {
                Move-Item $extractedNssm.FullName $NssmExe -Force
            }
            Write-Success "NSSM 安装完成: $NssmExe"
            return $true
        } else {
            Write-Error "NSSM 解压后未找到 nssm.exe"
            return $false
        }
    } catch {
        Write-Error "NSSM 安装失败: $_"
        return $false
    }
}

function Register-ChromaDBService {
    Write-Step "注册 ChromaDB 服务..." "CONFIGURING"

    # 检查 chroma 是否可用
    $chromaExe = Get-Command chroma.exe -ErrorAction SilentlyContinue
    if (-not $chromaExe) {
        Write-Error "chroma.exe 未找到！请先安装 ChromaDB: pip install chromadb"
        Write-Error "ChromaDB 服务注册失败"
        return $false
    }

    Write-Step "  ChromaDB 路径: $($chromaExe.Source)"

    # 确保数据目录存在
    if (-not (Test-Path $ChromaDataDir)) {
        New-Item -ItemType Directory -Path $ChromaDataDir -Force | Out-Null
    }

    if ($WhatIf) {
        Write-Warning "[WhatIf] 将注册服务: $ChromaServiceName"
        Write-Warning "  可执行文件: $($chromaExe.Source)"
        Write-Warning "  参数: run --host $ChromaHost --port $ChromaPort --path `"$ChromaDataDir`""
        return $true
    }

    # 停止并删除已存在的服务
    $existingService = Get-Service -Name $ChromaServiceName -ErrorAction SilentlyContinue
    if ($existingService) {
        Write-Step "  停止旧服务 $ChromaServiceName..." "STOPPING"
        Stop-Service -Name $ChromaServiceName -Force -ErrorAction SilentlyContinue
        & $NssmExe remove $ChromaServiceName confirm 2>&1 | Out-Null
    }

    # 使用 NSSM 注册服务
    $chromaArgs = "run --host $ChromaHost --port $ChromaPort --path `"$ChromaDataDir`""

    & $NssmExe install $ChromaServiceName $chromaExe.Source $chromaArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Error "NSSM 注册 ChromaDB 服务失败"
        return $false
    }

    # 配置工作目录
    & $NssmExe set $ChromaServiceName AppDirectory $RepoRoot

    # 配置自动恢复 (崩溃后 5 秒重启)
    & $NssmExe set $ChromaServiceName AppExit Default Restart
    & $NssmExe set $ChromaServiceName AppThrottle 5000

    # 配置日志输出
    $chromaLogDir = Join-Path $LogsDir "chromadb"
    if (-not (Test-Path $chromaLogDir)) {
        New-Item -ItemType Directory -Path $chromaLogDir -Force | Out-Null
    }
    & $NssmExe set $ChromaServiceName AppStdout (Join-Path $chromaLogDir "chromadb-stdout.log")
    & $NssmExe set $ChromaServiceName AppStderr (Join-Path $chromaLogDir "chromadb-stderr.log")
    & $NssmExe set $ChromaServiceName AppStdoutCreationDisposition 4
    & $NssmExe set $ChromaServiceName AppStderrCreationDisposition 4
    & $NssmExe set $ChromaServiceName AppRotateFiles 1
    & $NssmExe set $ChromaServiceName AppRotateOnline 0
    & $NssmExe set $ChromaServiceName AppRotateSeconds 86400
    & $NssmExe set $ChromaServiceName AppRotateBytes 10485760

    # 设置服务描述
    & $NssmExe set $ChromaServiceName Description "伏羲 Fuxi - ChromaDB 向量数据库服务 (端口 $ChromaPort)"

    # 设置启动类型为自动
    & $NssmExe set $ChromaServiceName Start SERVICE_AUTO_START

    Write-Success "ChromaDB 服务注册完成: $ChromaServiceName"
    return $true
}

function Register-MainService {
    Write-Step "注册 FastAPI (伏羲) 服务..." "CONFIGURING"

    $pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $pythonExe) {
        Write-Error "Python 未找到！请确保 Python 已安装并在 PATH 中。"
        return $false
    }

    Write-Step "  Python: $pythonExe"
    Write-Step "  工作目录: $MainWorkingDir"

    # 查找启动脚本
    $startScript = Join-Path $RepoRoot "start_server.py"
    if (-not (Test-Path $startScript)) {
        Write-Error "启动脚本未找到: $startScript"
        return $false
    }

    # 构建启动命令
    $startArgs = "-u `"$startScript`""

    if ($WhatIf) {
        Write-Warning "[WhatIf] 将注册服务: $MainServiceName"
        Write-Warning "  可执行文件: $pythonExe"
        Write-Warning "  参数: $startArgs"
        Write-Warning "  工作目录: $MainWorkingDir"
        return $true
    }

    # 停止并删除已存在的服务
    $existingService = Get-Service -Name $MainServiceName -ErrorAction SilentlyContinue
    if ($existingService) {
        Write-Step "  停止旧服务 $MainServiceName..." "STOPPING"
        Stop-Service -Name $MainServiceName -Force -ErrorAction SilentlyContinue
        & $NssmExe remove $MainServiceName confirm 2>&1 | Out-Null
    }

    # 使用 NSSM 注册服务
    & $NssmExe install $MainServiceName $pythonExe $startArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Error "NSSM 注册 FastAPI 服务失败"
        return $false
    }

    # 配置工作目录
    & $NssmExe set $MainServiceName AppDirectory $MainWorkingDir

    # 配置环境变量 (继承系统环境变量 + .env 文件)
    & $NssmExe set $MainServiceName AppEnvironmentExtra "KB_HOST=$MainHost"

    # 配置自动恢复 (崩溃后 5 秒重启)
    & $NssmExe set $MainServiceName AppExit Default Restart
    & $NssmExe set $MainServiceName AppThrottle 5000

    # 配置日志输出
    $mainLogDir = Join-Path $LogsDir "fuxi"
    if (-not (Test-Path $mainLogDir)) {
        New-Item -ItemType Directory -Path $mainLogDir -Force | Out-Null
    }
    & $NssmExe set $MainServiceName AppStdout (Join-Path $mainLogDir "fuxi-stdout.log")
    & $NssmExe set $MainServiceName AppStderr (Join-Path $mainLogDir "fuxi-stderr.log")
    & $NssmExe set $MainServiceName AppStdoutCreationDisposition 4
    & $NssmExe set $MainServiceName AppStderrCreationDisposition 4
    & $NssmExe set $MainServiceName AppRotateFiles 1
    & $NssmExe set $MainServiceName AppRotateOnline 0
    & $NssmExe set $MainServiceName AppRotateSeconds 86400
    & $NssmExe set $MainServiceName AppRotateBytes 10485760

    # 设置服务描述
    & $NssmExe set $MainServiceName Description "伏羲 Fuxi v1.44 - FastAPI 主服务 (端口 $MainPort)"

    # 设置启动类型为自动 (延迟启动，等 ChromaDB 先启动)
    & $NssmExe set $MainServiceName Start SERVICE_AUTO_START

    # 设置依赖关系：Fuxi-Main 依赖 Fuxi-ChromaDB
    & $NssmExe set $MainServiceName DependOnService $ChromaServiceName

    Write-Success "FastAPI 服务注册完成: $MainServiceName"
    return $true
}

function Unregister-Services {
    Write-Step "卸载所有伏羲服务..." "REMOVING"

    $services = @($ChromaServiceName, $MainServiceName)
    foreach ($svcName in $services) {
        $svc = Get-Service -Name $svcName -ErrorAction SilentlyContinue
        if ($svc) {
            Write-Step "  停止并删除 $svcName..." "REMOVING"

            if ($WhatIf) {
                Write-Warning "[WhatIf] 将删除服务: $svcName"
                continue
            }

            Stop-Service -Name $svcName -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
            & $NssmExe remove $svcName confirm 2>&1 | Out-Null
            Write-Success "  服务 $svcName 已删除"
        } else {
            Write-Warning "  服务 $svcName 未安装，跳过"
        }
    }

    Write-Success "服务卸载完成"
}

# ============================================================================
# 主流程
# ============================================================================

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  伏羲 Fuxi v1.44 - NSSM 进程守护安装脚本" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 检查管理员权限
Test-Admin

# 处理 WhatIf 模式
if ($WhatIf) {
    Write-Warning "====== 预览模式 (WhatIf) - 不会执行任何实际操作 ======"
    Write-Host ""
}

# 卸载模式
if ($Uninstall) {
    Install-Nssm | Out-Null
    Unregister-Services
    Write-Host ""
    Write-Host "卸载完成。如需重新安装，请运行:" -ForegroundColor Green
    Write-Host "  powershell -File scripts\install-services.ps1" -ForegroundColor Green
    exit 0
}

# 步骤 1: 安装 NSSM
Write-Host "--- 步骤 1: 安装 NSSM ---" -ForegroundColor Yellow
if (-not (Install-Nssm)) {
    Write-Error "NSSM 安装失败，无法继续。"
    exit 1
}
Write-Host ""

# 步骤 2: 创建必要的目录
Write-Host "--- 步骤 2: 创建目录 ---" -ForegroundColor Yellow
$dirs = @(
    $LogsDir,
    (Join-Path $LogsDir "chromadb"),
    (Join-Path $LogsDir "fuxi"),
    (Join-Path $LogsDir "watchdog")
)
foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        if (-not $WhatIf) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
        Write-Success "创建目录: $dir"
    }
}
Write-Host ""

# 步骤 3: 注册服务
$chromaOk = $true
$mainOk = $true

if ($Service -eq "All" -or $Service -eq "ChromaDB") {
    Write-Host "--- 步骤 3a: 注册 ChromaDB 服务 ---" -ForegroundColor Yellow
    $chromaOk = Register-ChromaDBService
    Write-Host ""
}

if ($Service -eq "All" -or $Service -eq "Main") {
    Write-Host "--- 步骤 3b: 注册 FastAPI 服务 ---" -ForegroundColor Yellow
    $mainOk = Register-MainService
    Write-Host ""
}

# 步骤 4: 显示服务状态
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  安装摘要" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "NSSM 路径  : $NssmExe"
Write-Host "脚本目录  : $ScriptDir"
Write-Host "项目目录  : $RepoRoot"
Write-Host ""

if ($Service -eq "All" -or $Service -eq "ChromaDB") {
    Write-Host "ChromaDB 服务:" -ForegroundColor Green
    if ($chromaOk) {
        Write-Host "  服务名    : $ChromaServiceName"
        Write-Host "  端口      : $ChromaPort"
        Write-Host "  数据目录  : $ChromaDataDir"
        Write-Host "  日志目录  : $LogsDir\chromadb\"
        Write-Host "  自动恢复  : 崩溃后 5 秒重启"
    } else {
        Write-Host "  状态      : 注册失败" -ForegroundColor Red
    }
    Write-Host ""
}

if ($Service -eq "All" -or $Service -eq "Main") {
    Write-Host "FastAPI 服务:" -ForegroundColor Green
    if ($mainOk) {
        Write-Host "  服务名    : $MainServiceName"
        Write-Host "  端口      : $MainPort"
        Write-Host "  工作目录  : $MainWorkingDir"
        Write-Host "  日志目录  : $LogsDir\fuxi\"
        Write-Host "  自动恢复  : 崩溃后 5 秒重启"
        Write-Host "  依赖服务  : $ChromaServiceName"
    } else {
        Write-Host "  状态      : 注册失败" -ForegroundColor Red
    }
    Write-Host ""
}

if (-not $WhatIf) {
    Write-Host "--- 管理命令 ---" -ForegroundColor Yellow
    Write-Host "启动 ChromaDB:   Start-Service $ChromaServiceName"
    Write-Host "启动 FastAPI:    Start-Service $MainServiceName"
    Write-Host "查看状态:         Get-Service $ChromaServiceName, $MainServiceName"
    Write-Host "停止 FastAPI:     Stop-Service $MainServiceName"
    Write-Host "停止 ChromaDB:   Stop-Service $ChromaServiceName"
    Write-Host "查看日志:         Get-Content $LogsDir\fuxi\fuxi-stdout.log -Tail 50"
    Write-Host ""
    Write-Host "提示: 也可通过 services.msc 图形界面管理这两个服务" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "安装脚本执行完毕。" -ForegroundColor Green
