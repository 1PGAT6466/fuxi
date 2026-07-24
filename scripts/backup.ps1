# ============================================================================
# 伏羲 Fuxi v1.44 - 备份恢复脚本 (backup.ps1)
# ============================================================================
# 功能:
#   1. Robocopy 增量备份 (仅复制变更文件，保留 ACL/时间戳)
#   2. SHA256 校验 (确保备份完整性)
#   3. 备份日志 (详细记录每次备份操作)
#
# 用法:
#   执行完整备份:     powershell -File scripts\backup.ps1
#   指定目标目录:     powershell -File scripts\backup.ps1 -Destination "D:\Backup\fuxi"
#   预览模式:         powershell -File scripts\backup.ps1 -WhatIf
#   仅备份数据:       powershell -File scripts\backup.ps1 -DataOnly
#   仅备份代码:       powershell -File scripts\backup.ps1 -CodeOnly
#   生成校验文件:     powershell -File scripts\backup.ps1 -ChecksumOnly
#   验证备份完整性:   powershell -File scripts\backup.ps1 -Verify -Source "D:\Backup\fuxi\2026-07-11"
# ============================================================================

param(
    [string]$Destination = "",
    [switch]$WhatIf,
    [switch]$DataOnly,
    [switch]$CodeOnly,
    [switch]$ChecksumOnly,
    [switch]$Verify,
    [string]$Source = "",
    [int]$RetentionDays = 30,
    [switch]$SkipChecksum,
    [switch]$NoRobocopy  # 仅生成校验文件（用于已有备份）
)

$ErrorActionPreference = "Continue"

# 路径配置
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$LogsDir = Join-Path $RepoRoot "logs"
$BackupLogFile = Join-Path $LogsDir "backup.log"

# 备份目标目录
$BackupDate = Get-Date -Format "yyyy-MM-dd_HHmm"
if (-not $Destination) {
    $Destination = Join-Path $RepoRoot "data\backups\$BackupDate"
}

# 校验文件路径
$ChecksumFile = Join-Path $Destination "backup_checksums.sha256"

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
        [ValidateSet("INFO", "SUCCESS", "WARN", "ERROR")]
        [string]$Level = "INFO"
    )

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"

    switch ($Level) {
        "SUCCESS" { Write-Host $logEntry -ForegroundColor Green }
        "ERROR"   { Write-Host $logEntry -ForegroundColor Red }
        "WARN"    { Write-Host $logEntry -ForegroundColor Yellow }
        default   { Write-Host $logEntry -ForegroundColor Gray }
    }

    Add-Content -Path $BackupLogFile -Value $logEntry -Encoding UTF8
}

function Write-Step {
    param([string]$Message)
    $timestamp = Get-Date -Format "HH:mm:ss"
    $line = "[$timestamp] $Message"
    Write-Host $line -ForegroundColor Cyan
}

function Format-Bytes {
    param([long]$Bytes)
    if ($Bytes -ge 1TB) { return "{0:N2} TB" -f ($Bytes / 1TB) }
    if ($Bytes -ge 1GB) { return "{0:N2} GB" -f ($Bytes / 1GB) }
    if ($Bytes -ge 1MB) { return "{0:N2} MB" -f ($Bytes / 1MB) }
    if ($Bytes -ge 1KB) { return "{0:N2} KB" -f ($Bytes / 1KB) }
    return "$Bytes B"
}

function Get-DirectorySize {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return 0 }

    try {
        $size = (Get-ChildItem -Path $Path -Recurse -File -ErrorAction SilentlyContinue |
                 Measure-Object -Property Length -Sum).Sum
        return $size
    } catch {
        return 0
    }
}

function Get-FileCount {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return 0 }

    try {
        $count = (Get-ChildItem -Path $Path -Recurse -File -ErrorAction SilentlyContinue).Count
        return $count
    } catch {
        return 0
    }
}

# ============================================================================
# Robocopy 增量备份
# ============================================================================

function Invoke-RobocopyBackup {
    param(
        [string]$SourcePath,
        [string]$DestPath,
        [string]$Description
    )

    if (-not (Test-Path $SourcePath)) {
        Write-Log "跳过 (源目录不存在): $SourcePath" -Level "WARN"
        return @{ Status = "SKIPPED"; Reason = "Source not found" }
    }

    # 确保目标目录存在
    if (-not (Test-Path $DestPath)) {
        if (-not $WhatIf) {
            New-Item -ItemType Directory -Path $DestPath -Force | Out-Null
        }
    }

    Write-Step "  备份 $Description"
    Write-Log "  [备份] 源: $SourcePath" -Level "INFO"
    Write-Log "  [备份] 目标: $DestPath" -Level "INFO"

    if ($WhatIf) {
        Write-Log "  [WhatIf] 将执行 Robocopy 增量备份: $Description" -Level "WARN"

        # 检查文件数量
        $fileCount = Get-FileCount -Path $SourcePath
        $dirSize = Get-DirectorySize -Path $SourcePath
        Write-Log "  [WhatIf] 源文件数: $fileCount, 源大小: $(Format-Bytes $dirSize)" -Level "INFO"
        return @{ Status = "WHATIF"; SourceFiles = $fileCount; SourceSize = $dirSize }
    }

    # 执行 Robocopy
    # /MIR   : 镜像目录 (增量复制 + 删除目标中多余文件)
    # /COPY:DAT : 复制数据、属性、时间戳
    # /R:3   : 重试 3 次
    # /W:5   : 重试间隔 5 秒
    # /NP    : 不显示进度百分比
    # /NDL   : 不显示目录列表
    # /NJH   : 不显示作业头
    # /NJS   : 不显示作业摘要
    # /XD    : 排除目录
    $robocopyArgs = @(
        $SourcePath,
        $DestPath,
        "/MIR",
        "/COPY:DAT",
        "/DCOPY:T",
        "/R:3",
        "/W:5",
        "/NP",
        "/NDL",
        "/NJH",
        "/NJS",
        "/XD", "__pycache__",
        "/XD", ".pytest_cache",
        "/XD", "node_modules",
        "/XD", ".git",
        "/XF", "*.pyc",
        "/XF", "*.pyo",
        "/XF", "*.tmp",
        "/XF", "*.bak",
        "/XF", "Thumbs.db",
        "/XF", ".DS_Store"
    )

    try {
        $result = robocopy @robocopyArgs
        $exitCode = $LASTEXITCODE

        # Robocopy 退出码: 0-7 表示成功 (8+ 表示错误)
        if ($exitCode -ge 8) {
            Write-Log "  [ERROR] Robocopy 返回错误码: $exitCode" -Level "ERROR"
            return @{ Status = "FAILED"; ExitCode = $exitCode }

        } else {
            Write-Log "  [OK] $Description 备份完成 (退出码: $exitCode)" -Level "SUCCESS"

            # 统计备份结果
            $destFileCount = Get-FileCount -Path $DestPath
            $destSize = Get-DirectorySize -Path $DestPath
            Write-Log "  [统计] 目标文件数: $destFileCount, 目标大小: $(Format-Bytes $destSize)" -Level "INFO"

            return @{
                Status      = "OK"
                ExitCode    = $exitCode
                FileCount   = $destFileCount
                Size        = $destSize
            }
        }
    } catch {
        Write-Log "  [ERROR] Robocopy 执行失败: $_" -Level "ERROR"
        return @{ Status = "FAILED"; Error = $_.Exception.Message }
    }
}

# ============================================================================
# SHA256 校验
# ============================================================================

function New-ChecksumFile {
    param(
        [string]$TargetPath,
        [string]$OutputFile
    )

    Write-Step "  生成 SHA256 校验文件..."
    Write-Log "  [校验] 扫描目录: $TargetPath" -Level "INFO"

    if (-not (Test-Path $TargetPath)) {
        Write-Log "  [WARN] 目录不存在，无法生成校验: $TargetPath" -Level "WARN"
        return @{ Status = "FAILED"; Reason = "Directory not found" }
    }

    if ($WhatIf) {
        $fileCount = Get-FileCount -Path $TargetPath
        Write-Log "  [WhatIf] 将为 $fileCount 个文件生成 SHA256 校验" -Level "WARN"
        return @{ Status = "WHATIF" }
    }

    try {
        $files = Get-ChildItem -Path $TargetPath -Recurse -File -ErrorAction SilentlyContinue |
                 Where-Object { $_.Name -ne "backup_checksums.sha256" }

        $totalFiles = $files.Count
        $processed = 0
        $hashCount = 0
        $errorCount = 0

        # 创建或清空校验文件
        $header = @"
# ============================================================================
# 伏羲 Fuxi v1.44 - 备份校验文件
# 生成时间: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
# 备份目录: $TargetPath
# 文件总数: $totalFiles
# ============================================================================

"@
        $header | Out-File -FilePath $OutputFile -Encoding UTF8 -Force

        foreach ($file in $files) {
            $processed++

            # 进度显示 (每 100 个文件)
            if ($processed % 100 -eq 0) {
                Write-Host "`r  校验进度: $processed / $totalFiles" -NoNewline
            }

            try {
                # 跳过超大文件 (大于 1GB)
                if ($file.Length -gt 1GB) {
                    $hash = "SKIPPED (文件过大: $(Format-Bytes $file.Length))"
                    $errorCount++
                } else {
                    $hash = (Get-FileHash -Path $file.FullName -Algorithm SHA256).Hash
                    $hashCount++
                }

                # 获取相对路径
                $relativePath = $file.FullName.Substring($TargetPath.Length).TrimStart('\', '/')

                # 写入校验行: HASH *相对路径
                "$hash *$relativePath" | Out-File -FilePath $OutputFile -Encoding UTF8 -Append

            } catch {
                $relativePath = $file.FullName.Substring($TargetPath.Length).TrimStart('\', '/')
                "ERROR:$_ *$relativePath" | Out-File -FilePath $OutputFile -Encoding UTF8 -Append
                $errorCount++
            }
        }

        if ($processed -gt 0) {
            Write-Host ""  # 换行
        }

        Write-Log "  [OK] 校验文件生成完成: $(Split-Path $OutputFile -Leaf)" -Level "SUCCESS"
        Write-Log "  [统计] 总计: $totalFiles 文件, 成功: $hashCount, 跳过/错误: $errorCount" -Level "INFO"

        return @{
            Status      = "OK"
            TotalFiles  = $totalFiles
            HashCount   = $hashCount
            ErrorCount  = $errorCount
            OutputFile  = $OutputFile
        }

    } catch {
        Write-Log "  [ERROR] 校验文件生成失败: $_" -Level "ERROR"
        return @{ Status = "FAILED"; Error = $_.Exception.Message }
    }
}

function Test-BackupIntegrity {
    param(
        [string]$BackupPath,
        [string]$ChecksumFilePath
    )

    Write-Step "  验证备份完整性..."
    Write-Log "  [验证] 备份目录: $BackupPath" -Level "INFO"

    if (-not (Test-Path $ChecksumFilePath)) {
        Write-Log "  [WARN] 校验文件不存在: $ChecksumFilePath" -Level "WARN"
        Write-Log "  [提示] 请先生成校验文件: powershell -File scripts\backup.ps1 -ChecksumOnly -Source <备份目录>" -Level "INFO"
        return @{ Status = "FAILED"; Reason = "Checksum file not found" }
    }

    if (-not (Test-Path $BackupPath)) {
        Write-Log "  [ERROR] 备份目录不存在: $BackupPath" -Level "ERROR"
        return @{ Status = "FAILED"; Reason = "Backup directory not found" }
    }

    try {
        $checksums = Get-Content -Path $ChecksumFilePath -Encoding UTF8 |
                     Where-Object { $_ -match '^[A-Fa-f0-9]{64}\s+\*' }

        $total = $checksums.Count
        $verified = 0
        $mismatch = 0
        $missing = 0
        $error = 0

        $mismatchList = @()

        foreach ($line in $checksums) {
            if ($line -match '^([A-Fa-f0-9]{64})\s+\*(.+)$') {
                $expectedHash = $Matches[1]
                $relativePath = $Matches[2]
                $fullPath = Join-Path $BackupPath $relativePath

                if (-not (Test-Path $fullPath)) {
                    $missing++
                    $mismatchList += "[MISSING] $relativePath"
                    continue
                }

                try {
                    $actualHash = (Get-FileHash -Path $fullPath -Algorithm SHA256).Hash
                    if ($actualHash -eq $expectedHash) {
                        $verified++
                    } else {
                        $mismatch++
                        $mismatchList += "[MISMATCH] $relativePath (期望: $expectedHash, 实际: $actualHash)"
                    }
                } catch {
                    $error++
                    $mismatchList += "[ERROR] $relativePath ($_)"
                }
            }
        }

        Write-Host ""
        Write-Log "  [验证结果]" -Level "INFO"
        Write-Log "    总计: $total" -Level "INFO"

        if ($verified -gt 0) {
            Write-Log "    通过: $verified" -ForegroundColor Green
        }
        if ($mismatch -gt 0) {
            Write-Log "    不匹配: $mismatch" -Level "ERROR"
            foreach ($item in $mismatchList) {
                Write-Log "      $item" -Level "ERROR"
            }
        }
        if ($missing -gt 0) {
            Write-Log "    缺失: $missing" -Level "ERROR"
        }
        if ($error -gt 0) {
            Write-Log "    错误: $error" -Level "ERROR"
        }

        if ($mismatch -eq 0 -and $missing -eq 0 -and $error -eq 0) {
            Write-Log "  [OK] 备份完整性验证通过！所有文件校验一致。" -Level "SUCCESS"
            return @{ Status = "OK"; Verified = $verified; Total = $total }
        } else {
            Write-Log "  [WARN] 备份完整性验证未通过！请检查上述问题。" -Level "WARN"
            return @{ Status = "FAILED"; Verified = $verified; Total = $total;
                      Mismatch = $mismatch; Missing = $missing; Error = $error }
        }

    } catch {
        Write-Log "  [ERROR] 验证过程异常: $_" -Level "ERROR"
        return @{ Status = "FAILED"; Error = $_.Exception.Message }
    }
}

# ============================================================================
# 备份清理
# ============================================================================

function Remove-OldBackups {
    param(
        [string]$BackupsRoot,
        [int]$RetentionDays
    )

    if (-not (Test-Path $BackupsRoot)) { return }

    Write-Step "清理 $RetentionDays 天前的旧备份..."

    $cutoffDate = (Get-Date).AddDays(-$RetentionDays)

    try {
        $oldBackups = Get-ChildItem -Path $BackupsRoot -Directory |
                      Where-Object { $_.LastWriteTime -lt $cutoffDate }

        foreach ($old in $oldBackups) {
            $size = Get-DirectorySize -Path $old.FullName
            if ($WhatIf) {
                Write-Log "  [WhatIf] 将删除旧备份: $($old.Name) ($(Format-Bytes $size))" -Level "WARN"
            } else {
                try {
                    Remove-Item -Path $old.FullName -Recurse -Force
                    Write-Log "  [已删除] $($old.Name) ($(Format-Bytes $size))" -Level "INFO"
                } catch {
                    Write-Log "  [ERROR] 无法删除: $($old.Name) - $_" -Level "ERROR"
                }
            }
        }

        if ($oldBackups.Count -eq 0) {
            Write-Log "  没有需要清理的旧备份" -Level "INFO"
        }

    } catch {
        Write-Log "  [ERROR] 清理过程异常: $_" -Level "ERROR"
    }
}

# ============================================================================
# 仅校验模式
# ============================================================================

function Invoke-ChecksumOnly {
    param([string]$SourcePath)

    if (-not $SourcePath) {
        Write-Log "请指定要生成校验的备份目录: -Source <路径>" -Level "ERROR"
        exit 1
    }

    if (-not (Test-Path $SourcePath)) {
        Write-Log "目录不存在: $SourcePath" -Level "ERROR"
        exit 1
    }

    Write-Host ""
    Write-Host "===== 仅生成校验文件模式 =====" -ForegroundColor Yellow
    Write-Host ""

    $checksumPath = Join-Path $SourcePath "backup_checksums.sha256"
    $result = New-ChecksumFile -TargetPath $SourcePath -OutputFile $checksumPath

    Write-Host ""
    Write-Host "校验文件: $checksumPath" -ForegroundColor Green
    exit 0
}

# ============================================================================
# 主流程
# ============================================================================

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  伏羲 Fuxi v1.44 - 备份恢复脚本" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "项目目录   : $RepoRoot" -ForegroundColor Gray
Write-Host "备份目标   : $Destination" -ForegroundColor Gray
Write-Host "备份日志   : $BackupLogFile" -ForegroundColor Gray
if ($WhatIf) {
    Write-Host "模式       : 预览 (WhatIf)" -ForegroundColor Yellow
}
Write-Host ""

# 记录开始
Write-Log "==================== 备份任务开始 ====================" -Level "INFO"

$startTime = Get-Date

# 仅校验模式
if ($ChecksumOnly) {
    Invoke-ChecksumOnly -SourcePath $Source
}

# 验证模式
if ($Verify) {
    Write-Host "===== 备份完整性验证模式 =====" -ForegroundColor Yellow
    Write-Host ""

    if (-not $Source) {
        Write-Log "请指定备份目录: -Source <备份目录路径>" -Level "ERROR"
        exit 1
    }

    $checksumPath = Join-Path $Source "backup_checksums.sha256"
    $verifyResult = Test-BackupIntegrity -BackupPath $Source -ChecksumFilePath $checksumPath

    Write-Host ""
    if ($verifyResult.Status -eq "OK") {
        Write-Host "备份完整性验证通过！" -ForegroundColor Green
    } else {
        Write-Host "备份完整性验证未通过！" -ForegroundColor Red
    }

    Write-Log "==================== 备份任务结束 ====================" -Level "INFO"
    exit 0
}

# 仅生成校验模式 (对已有备份)
if ($NoRobocopy) {
    if (-not $Source) {
        Write-Log "请指定备份目录: -Source <备份目录路径>" -Level "ERROR"
        exit 1
    }
    Invoke-ChecksumOnly -SourcePath $Source
}

# 备份清单
$backupTasks = @()

if ($DataOnly) {
    $backupTasks += @{
        Source      = Join-Path $RepoRoot "data"
        Dest        = Join-Path $Destination "data"
        Description = "数据目录 (data/)"
    }
} elseif ($CodeOnly) {
    $backupTasks += @{
        Source      = Join-Path $RepoRoot "src"
        Dest        = Join-Path $Destination "src"
        Description = "源代码 (src/)"
    }
    $backupTasks += @{
        Source      = Join-Path $RepoRoot "config"
        Dest        = Join-Path $Destination "config"
        Description = "配置目录 (config/)"
    }
    $backupTasks += @{
        Source      = Join-Path $RepoRoot "scripts"
        Dest        = Join-Path $Destination "scripts"
        Description = "脚本目录 (scripts/)"
    }
    $backupTasks += @{
        Source      = Join-Path $RepoRoot "frontend"
        Dest        = Join-Path $Destination "frontend"
        Description = "前端 (frontend/)"
    }
} else {
    # 完整备份
    $backupTasks += @{
        Source      = Join-Path $RepoRoot "src"
        Dest        = Join-Path $Destination "src"
        Description = "源代码 (src/)"
    }
    $backupTasks += @{
        Source      = Join-Path $RepoRoot "config"
        Dest        = Join-Path $Destination "config"
        Description = "配置目录 (config/)"
    }
    $backupTasks += @{
        Source      = Join-Path $RepoRoot "scripts"
        Dest        = Join-Path $Destination "scripts"
        Description = "脚本目录 (scripts/)"
    }
    $backupTasks += @{
        Source      = Join-Path $RepoRoot "data"
        Dest        = Join-Path $Destination "data"
        Description = "数据目录 (data/)"
    }
    $backupTasks += @{
        Source      = Join-Path $RepoRoot "frontend"
        Dest        = Join-Path $Destination "frontend"
        Description = "前端 (frontend/)"
    }
    $backupTasks += @{
        Source      = Join-Path $RepoRoot "deploy"
        Dest        = Join-Path $Destination "deploy"
        Description = "部署目录 (deploy/)"
    }
    $backupTasks += @{
        Source      = Join-Path $RepoRoot "docs"
        Dest        = Join-Path $Destination "docs"
        Description = "文档目录 (docs/)"
    }
}

# 执行备份
Write-Host "--- 步骤 1: 执行 Robocopy 增量备份 ---" -ForegroundColor Yellow
$results = @()
$backupSuccess = $true

foreach ($task in $backupTasks) {
    $result = Invoke-RobocopyBackup -SourcePath $task.Source -DestPath $task.Dest -Description $task.Description
    $results += $result
    if ($result.Status -eq "FAILED") {
        $backupSuccess = $false
    }
}
Write-Host ""

# 备份关键配置文件
Write-Host "--- 步骤 2: 备份关键配置文件 ---" -ForegroundColor Yellow
$criticalFiles = @(
    @{ Name = ".env"; Path = Join-Path $RepoRoot ".env" },
    @{ Name = "requirements.txt"; Path = Join-Path $RepoRoot "requirements.txt" },
    @{ Name = "docker-compose.yml"; Path = Join-Path $RepoRoot "docker-compose.yml" },
    @{ Name = "Dockerfile"; Path = Join-Path $RepoRoot "Dockerfile" }
)

foreach ($file in $criticalFiles) {
    if (Test-Path $file.Path) {
        $destFile = Join-Path $Destination $file.Name
        if (-not $WhatIf) {
            Copy-Item -Path $file.Path -Destination $destFile -Force
        }
        Write-Log "  [OK] 关键文件: $($file.Name)" -Level "SUCCESS"
    } else {
        Write-Log "  [SKIP] 关键文件不存在: $($file.Name)" -Level "WARN"
    }
}
Write-Host ""

# 生成校验文件
if (-not $SkipChecksum) {
    Write-Host "--- 步骤 3: 生成 SHA256 校验文件 ---" -ForegroundColor Yellow
    $checksumResult = New-ChecksumFile -TargetPath $Destination -OutputFile $ChecksumFile
    Write-Host ""
}

# 创建备份元数据
Write-Host "--- 步骤 4: 生成备份元数据 ---" -ForegroundColor Yellow
$metadata = @"
# 伏羲 Fuxi v1.44 - 备份元数据
备份时间: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
备份类型: $(if ($DataOnly) { "仅数据" } elseif ($CodeOnly) { "仅代码" } else { "完整备份" })
备份来源: $RepoRoot
备份目标: $Destination
备份状态: $(if ($backupSuccess) { "成功" } else { "部分失败" })

## 备份清单
"@

foreach ($task in $backupTasks) {
    $destSize = Get-DirectorySize -Path $task.Dest
    $destFiles = Get-FileCount -Path $task.Dest
    $metadata += "`n- $($task.Description): $destFiles 文件, $(Format-Bytes $destSize)"
}

$metadata += @"

## 系统信息
主机名: $env:COMPUTERNAME
登录用户: $env:USERNAME
操作系统: $(Get-CimInstance -ClassName Win32_OperatingSystem | Select-Object -ExpandProperty Caption)
内存: $(Format-Bytes ((Get-CimInstance -ClassName Win32_OperatingSystem).TotalVisibleMemorySize * 1024))
"@

$metadataFile = Join-Path $Destination "BACKUP_INFO.md"
if (-not $WhatIf) {
    $metadata | Out-File -FilePath $metadataFile -Encoding UTF8 -Force
    Write-Log "  [OK] 元数据文件: BACKUP_INFO.md" -Level "SUCCESS"
}
Write-Host ""

# 清理旧备份
Write-Host "--- 步骤 5: 清理旧备份 ---" -ForegroundColor Yellow
$backupsRoot = Join-Path $RepoRoot "data\backups"
Remove-OldBackups -BackupsRoot $backupsRoot -RetentionDays $RetentionDays
Write-Host ""

# 统计汇总
$endTime = Get-Date
$elapsed = $endTime - $startTime

$totalFiles = 0
$totalSize = 0
foreach ($task in $backupTasks) {
    $destSize = Get-DirectorySize -Path $task.Dest
    $destFiles = Get-FileCount -Path $task.Dest
    $totalFiles += $destFiles
    $totalSize += $destSize
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  备份摘要" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "备份目录   : $Destination"
Write-Host "备份方式   : Robocopy 增量镜像"
Write-Host "文件总数   : $totalFiles"
Write-Host "总大小     : $(Format-Bytes $totalSize)"
Write-Host "耗时       : $($elapsed.ToString('hh\:mm\:ss'))"
Write-Host "校验文件   : $(Split-Path $ChecksumFile -Leaf)"
Write-Host "元数据     : BACKUP_INFO.md"
Write-Host "状态       : $(if ($backupSuccess) { '成功' } else { '部分失败（请检查日志）' })"

if (-not $WhatIf -and $backupSuccess) {
    Write-Host ""
    Write-Host "备份完成。验证备份完整性:" -ForegroundColor Green
    Write-Host "  powershell -File scripts\backup.ps1 -Verify -Source `"$Destination`"" -ForegroundColor Gray
}

Write-Host ""

Write-Log "备份任务完成 - 状态: $(if ($backupSuccess) { '成功' } else { '部分失败' }) - 耗时: $($elapsed.ToString('hh\:mm\:ss'))" -Level "INFO"
Write-Log "==================== 备份任务结束 ====================" -Level "INFO"
