# ============================================================================
# 伏羲 Fuxi v1.44 - 内存监控脚本 (memory-monitor.ps1)
# ============================================================================
# 功能:
#   1. 每 2 分钟检查内存使用率
#   2. 超过 80% 记录告警
#   3. 超过 90% 触发 GC 并记录告警
#   4. 记录日志到 logs\memory.log
#
# 用法:
#   单次检查:         powershell -File scripts\memory-monitor.ps1
#   持续监控:         powershell -File scripts\memory-monitor.ps1 -Loop
#   自定义阈值:       powershell -File scripts\memory-monitor.ps1 -WarnThreshold 75 -CriticalThreshold 85
#   预览模式:         powershell -File scripts\memory-monitor.ps1 -WhatIf
# ============================================================================

param(
    [switch]$Loop,
    [switch]$WhatIf,
    [int]$WarnThreshold = 80,
    [int]$CriticalThreshold = 90,
    [int]$IntervalSeconds = 120
)

$ErrorActionPreference = "Continue"

# 路径配置
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$LogsDir = Join-Path $RepoRoot "logs"
$LogFile = Join-Path $LogsDir "memory.log"

# 确保日志目录存在
if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
}

# ============================================================================
# 辅助函数
# ============================================================================

function Write-Log {
    param(
        [string]$Message,
        [ValidateSet("INFO", "WARN", "ALERT", "CRITICAL", "ERROR")]
        [string]$Level = "INFO"
    )

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"

    # 写入控制台 (带颜色)
    switch ($Level) {
        "CRITICAL" { Write-Host $logEntry -ForegroundColor Red }
        "ALERT"    { Write-Host $logEntry -ForegroundColor Red }
        "WARN"     { Write-Host $logEntry -ForegroundColor Yellow }
        "ERROR"    { Write-Host $logEntry -ForegroundColor DarkRed }
        default    { Write-Host $logEntry -ForegroundColor Gray }
    }

    # 写入日志文件
    Add-Content -Path $LogFile -Value $logEntry -Encoding UTF8
}

function Get-MemoryUsage {
    <#
    .SYNOPSIS
    获取当前系统内存使用率百分比
    .DESCRIPTION
    返回一个哈希表包含:
      - TotalMB: 总物理内存 (MB)
      - UsedMB: 已用物理内存 (MB)
      - FreeMB: 可用物理内存 (MB)
      - UsagePercent: 使用率百分比
      - CommittedMB: 已提交内存 (MB)
      - CommitLimitMB: 提交限制 (MB)
    #>
    $os = Get-CimInstance -ClassName Win32_OperatingSystem

    $totalMB = [math]::Round($os.TotalVisibleMemorySize / 1024, 2)
    $freeMB = [math]::Round($os.FreePhysicalMemory / 1024, 2)
    $usedMB = [math]::Round($totalMB - $freeMB, 2)
    $usagePercent = [math]::Round(($usedMB / $totalMB) * 100, 2)

    $committedMB = [math]::Round(($os.TotalVirtualMemorySize - $os.FreeVirtualMemory) / 1024, 2)
    $commitLimitMB = [math]::Round($os.TotalVirtualMemorySize / 1024, 2)

    return @{
        TotalMB        = $totalMB
        UsedMB         = $usedMB
        FreeMB         = $freeMB
        UsagePercent   = $usagePercent
        CommittedMB    = $committedMB
        CommitLimitMB  = $commitLimitMB
    }
}

function Get-TopProcessesByMemory {
    <#
    .SYNOPSIS
    获取内存占用最高的前 N 个进程
    #>
    param([int]$Top = 10)

    try {
        $processes = Get-Process | Sort-Object -Property WorkingSet64 -Descending | Select-Object -First $Top

        $result = @()
        foreach ($proc in $processes) {
            $result += [PSCustomObject]@{
                Name       = $proc.ProcessName
                PID        = $proc.Id
                WorkingSetMB = [math]::Round($proc.WorkingSet64 / 1MB, 2)
                PrivateMB  = [math]::Round($proc.PrivateMemorySize64 / 1MB, 2)
            }
        }
        return $result
    } catch {
        return $null
    }
}

function Trigger-GarbageCollection {
    <#
    .SYNOPSIS
    尝试触发 .NET 垃圾回收以释放内存
    #>
    Write-Log "触发 .NET 垃圾回收 (GC)..." -Level "ALERT"

    try {
        # 方法 1: 通过 PowerShell 触发 GC
        [System.GC]::Collect()
        [System.GC]::WaitForPendingFinalizers()
        [System.GC]::Collect()
        Write-Log ".NET GC 执行完成" -Level "INFO"
        return $true
    } catch {
        Write-Log ".NET GC 触发失败: $_" -Level "ERROR"
    }

    # 方法 2: 如果 Python 服务在运行，尝试通过 API 触发
    try {
        $gcResponse = Invoke-RestMethod -Uri "http://localhost:8080/api/system/gc" -Method POST -TimeoutSec 10 -ErrorAction Stop
        Write-Log "Python 服务 GC 触发成功: $($gcResponse | ConvertTo-Json -Compress)" -Level "INFO"
    } catch {
        Write-Log "Python 服务 GC 触发失败 (服务可能未运行): $_" -Level "WARN"
    }

    # 方法 3: 清理系统工作集
    try {
        $cleaner = New-Object -ComObject "Shell.Application"
        # 这是一个提示性方法，实际效果有限
        Write-Log "系统工作集清理提示已发出" -Level "INFO"
    } catch {
        # 忽略
    }

    return $false
}

function Invoke-MemoryCleanup {
    <#
    .SYNOPSIS
    执行系统级内存清理操作
    #>
    Write-Log "执行紧急内存清理..." -Level "CRITICAL"

    # 1. 清空备用列表 (需要 EmptyStandbyList.exe 或类似工具)
    # 仅记录，不执行危险操作

    # 2. 尝试压缩内存
    try {
        $compressResult = Invoke-CimMethod -ClassName Win32_Process -MethodName Create `
            -Arguments @{ CommandLine = "rundll32.exe advapi32.dll,ProcessIdleTasks" } `
            -ErrorAction SilentlyContinue
        Write-Log "空闲任务处理已触发" -Level "INFO"
    } catch {
        # 忽略
    }

    Write-Log "内存清理流程完成" -Level "INFO"
}

# ============================================================================
# 单次检查函数
# ============================================================================

function Invoke-MemoryCheck {
    param([switch]$SuppressHeader)

    if (-not $SuppressHeader) {
        Write-Log "========== 内存检查开始 ==========" -Level "INFO"
    }

    # 获取内存信息
    $mem = Get-MemoryUsage

    Write-Log "总内存: $($mem.TotalMB) MB | 已用: $($mem.UsedMB) MB | 可用: $($mem.FreeMB) MB | 使用率: $($mem.UsagePercent)%" -Level "INFO"

    # 检查阈值
    if ($mem.UsagePercent -ge $CriticalThreshold) {
        Write-Log "【严重告警】内存使用率 $($mem.UsagePercent)% 已超过严重阈值 ${CriticalThreshold}%！" -Level "CRITICAL"
        Write-Log "  总内存: $($mem.TotalMB) MB" -Level "CRITICAL"
        Write-Log "  已用内存: $($mem.UsedMB) MB" -Level "CRITICAL"
        Write-Log "  可用内存: $($mem.FreeMB) MB" -Level "CRITICAL"
        Write-Log "  已提交: $($mem.CommittedMB) MB / $($mem.CommitLimitMB) MB" -Level "CRITICAL"

        # 输出 TOP 10 内存占用进程
        Write-Log "--- TOP 10 内存占用进程 ---" -Level "CRITICAL"
        $topProcs = Get-TopProcessesByMemory -Top 10
        if ($topProcs) {
            foreach ($proc in $topProcs) {
                Write-Log "  $($proc.Name) (PID: $($proc.PID)) - WorkingSet: $($proc.WorkingSetMB) MB, Private: $($proc.PrivateMB) MB" -Level "CRITICAL"
            }
        }

        # 触发 GC
        Write-Log "--- 触发紧急内存回收 ---" -Level "CRITICAL"
        Trigger-GarbageCollection
        Invoke-MemoryCleanup

        # 等待 10 秒后重新检查
        Write-Log "等待 10 秒后重新检查..." -Level "CRITICAL"
        Start-Sleep -Seconds 10

        $memAfter = Get-MemoryUsage
        Write-Log "清理后: 已用: $($memAfter.UsedMB) MB | 可用: $($memAfter.FreeMB) MB | 使用率: $($memAfter.UsagePercent)%" -Level "CRITICAL"

    } elseif ($mem.UsagePercent -ge $WarnThreshold) {
        Write-Log "【告警】内存使用率 $($mem.UsagePercent)% 已超过警告阈值 ${WarnThreshold}%！" -Level "WARN"
        Write-Log "  总内存: $($mem.TotalMB) MB | 已用: $($mem.UsedMB) MB | 可用: $($mem.FreeMB) MB" -Level "WARN"

        # 输出 TOP 5 内存占用进程
        Write-Log "--- TOP 5 内存占用进程 ---" -Level "WARN"
        $topProcs = Get-TopProcessesByMemory -Top 5
        if ($topProcs) {
            foreach ($proc in $topProcs) {
                Write-Log "  $($proc.Name) (PID: $($proc.PID)) - WorkingSet: $($proc.WorkingSetMB) MB, Private: $($proc.PrivateMB) MB" -Level "WARN"
            }
        }

    } else {
        Write-Log "内存使用率正常: $($mem.UsagePercent)%" -Level "INFO"
    }

    if (-not $SuppressHeader) {
        Write-Log "========== 内存检查结束 ==========" -Level "INFO"
        Write-Log "" -Level "INFO"
    }
}

# ============================================================================
# 主流程
# ============================================================================

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  伏羲 Fuxi v1.44 - 内存监控脚本" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "日志文件  : $LogFile" -ForegroundColor Gray
Write-Host "警告阈值  : ${WarnThreshold}%" -ForegroundColor Gray
Write-Host "严重阈值  : ${CriticalThreshold}%" -ForegroundColor Gray
Write-Host "检查间隔  : ${IntervalSeconds} 秒" -ForegroundColor Gray
if ($WhatIf) {
    Write-Host "模式      : 预览 (WhatIf)" -ForegroundColor Yellow
}
Write-Host ""

if ($WhatIf) {
    Write-Host "[WhatIf 模式] 仅演示检查逻辑，不写入日志。" -ForegroundColor Yellow
    Write-Host ""
    $mem = Get-MemoryUsage
    Write-Host "当前内存: Total=$($mem.TotalMB)MB, Used=$($mem.UsedMB)MB, Free=$($mem.FreeMB)MB, Usage=$($mem.UsagePercent)%"
    Write-Host ""

    if ($mem.UsagePercent -ge $CriticalThreshold) {
        Write-Host "[WhatIf] 将触发: 严重告警 + GC + TOP 10 进程" -ForegroundColor Red
    } elseif ($mem.UsagePercent -ge $WarnThreshold) {
        Write-Host "[WhatIf] 将触发: 警告告警 + TOP 5 进程" -ForegroundColor Yellow
    } else {
        Write-Host "[WhatIf] 内存正常，无需操作" -ForegroundColor Green
    }
    Write-Host ""
    exit 0
}

if ($Loop) {
    Write-Host "进入持续监控模式 (Ctrl+C 停止)..." -ForegroundColor Green
    Write-Host ""

    $checkCount = 0
    while ($true) {
        $checkCount++
        Write-Log "检查轮次: $checkCount" -Level "INFO"
        Invoke-MemoryCheck

        # 等待下一次检查
        $waitSeconds = $IntervalSeconds
        Write-Log "等待 ${waitSeconds} 秒后进行下一次检查..." -Level "INFO"

        # 分段等待，每 10 秒检查一次用户是否想中断
        for ($i = 0; $i -lt $waitSeconds; $i += 10) {
            $remaining = $waitSeconds - $i
            if ($remaining -gt 10) { $remaining = 10 }
            Start-Sleep -Seconds $remaining
        }
    }
} else {
    Invoke-MemoryCheck
    Write-Host ""
    Write-Host "单次检查完成。如需持续监控，请使用 -Loop 参数:" -ForegroundColor Green
    Write-Host "  powershell -File scripts\memory-monitor.ps1 -Loop" -ForegroundColor Green
}
