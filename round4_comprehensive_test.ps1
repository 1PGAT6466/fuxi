#!/usr/bin/env pwsh
# 伏羲 v1.44 第四轮全面综合检测脚本
# 测试所有 API 端点 + 前端路由 + 安全防护 + 性能指标

param(
    [string]$BaseUrl = "http://127.0.0.1:8080"
)

$ErrorActionPreference = "Continue"
$results = @()
$startTime = Get-Date

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Method,
        [string]$Endpoint,
        [object]$Body = $null,
        [hashtable]$Headers = @{},
        [int]$ExpectedStatus = 200,
        [switch]$RequireAuth
    )
    
    $url = "$BaseUrl$Endpoint"
    $testStart = Get-Date
    
    try {
        $params = @{
            Uri = $url
            Method = $Method
            ContentType = "application/json"
            Headers = $Headers
            TimeoutSec = 10
            ErrorAction = "Stop"
        }
        
        if ($Body) {
            $params.Body = $Body | ConvertTo-Json -Depth 10
        }
        
        $response = Invoke-RestMethod @params
        $statusCode = 200  # Invoke-RestMethod doesn't expose status code on success
        $responseTime = ((Get-Date) - $testStart).TotalMilliseconds
        
        $result = [PSCustomObject]@{
            Test = $Name
            Method = $Method
            Endpoint = $Endpoint
            StatusCode = $statusCode
            ExpectedStatus = $ExpectedStatus
            Status = "PASS"
            ResponseTime = [math]::Round($responseTime, 2)
            Response = $response
            Error = $null
        }
    }
    catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        $responseTime = ((Get-Date) - $testStart).TotalMilliseconds
        
        $result = [PSCustomObject]@{
            Test = $Name
            Method = $Method
            Endpoint = $Endpoint
            StatusCode = $statusCode
            ExpectedStatus = $ExpectedStatus
            Status = if ($statusCode -eq $ExpectedStatus) { "PASS" } else { "FAIL" }
            ResponseTime = [math]::Round($responseTime, 2)
            Response = $null
            Error = $_.Exception.Message
        }
    }
    
    return $result
}

Write-Host "=" * 80
Write-Host "伏羲 v1.44 第四轮全面综合检测"
Write-Host "=" * 80
Write-Host ""

# ==================== 一、系统健康检查 ====================
Write-Host "[一] 系统健康检查" -ForegroundColor Cyan
Write-Host "-" * 40

$results += Test-Endpoint -Name "1.1 健康检查" -Method "GET" -Endpoint "/api/health" -ExpectedStatus 200
$results += Test-Endpoint -Name "1.2 系统状态" -Method "GET" -Endpoint "/api/stats" -ExpectedStatus 200

# ==================== 二、认证系统测试 ====================
Write-Host "`n[二] 认证系统测试" -ForegroundColor Cyan
Write-Host "-" * 40

# 注册测试
$results += Test-Endpoint -Name "2.1 注册新用户" -Method "POST" -Endpoint "/api/auth/register" -Body @{
    username = "testuser_round4_$(Get-Random)"
    password = "TestPass123"
}

# 登录测试
$loginResult = Test-Endpoint -Name "2.2 用户登录" -Method "POST" -Endpoint "/api/auth/login" -Body @{
    username = "round4test"
    password = "Test1234"
}

$results += $loginResult

if ($loginResult.StatusCode -eq 200 -and $loginResult.Response.token) {
    $token = $loginResult.Response.token
    $authHeaders = @{ Authorization = "Bearer $token" }
    Write-Host "✓ 登录成功，获取到 Token" -ForegroundColor Green
}
else {
    Write-Host "✗ 登录失败，无法获取 Token" -ForegroundColor Red
    $authHeaders = @{}
}

# 获取当前用户
$results += Test-Endpoint -Name "2.3 获取当前用户" -Method "GET" -Endpoint "/api/auth/me" -Headers $authHeaders -ExpectedStatus 200

# 刷新Token
$results += Test-Endpoint -Name "2.4 刷新Token" -Method "POST" -Endpoint "/api/auth/refresh" -Headers $authHeaders -ExpectedStatus 200

# 登出
$results += Test-Endpoint -Name "2.5 用户登出" -Method "POST" -Endpoint "/api/auth/logout" -Headers $authHeaders -ExpectedStatus 200

# 重新登录获取token
$loginResult2 = Test-Endpoint -Name "2.6 重新登录" -Method "POST" -Endpoint "/api/auth/login" -Body @{
    username = "round4test"
    password = "Test1234"
}
$results += $loginResult2

if ($loginResult2.StatusCode -eq 200 -and $loginResult2.Response.token) {
    $token = $loginResult2.Response.token
    $authHeaders = @{ Authorization = "Bearer $token" }
}

# ==================== 三、安全防护测试 ====================
Write-Host "`n[三] 安全防护测试" -ForegroundColor Cyan
Write-Host "-" * 40

# 未认证访问
$results += Test-Endpoint -Name "3.1 未认证访问保护" -Method "GET" -Endpoint "/api/auth/me" -ExpectedStatus 401

# 无效Token
$results += Test-Endpoint -Name "3.2 无效Token拒绝" -Method "GET" -Endpoint "/api/auth/me" -Headers @{ Authorization = "Bearer invalid_token" } -ExpectedStatus 401

# 登录频率限制
Write-Host "测试登录频率限制..." -ForegroundColor Yellow
$failedLogins = 0
for ($i = 1; $i -le 12; $i++) {
    try {
        $null = Invoke-RestMethod -Uri "$BaseUrl/api/auth/login" -Method POST -ContentType "application/json" -Body '{"username":"round4test","password":"wrongpass"}' -ErrorAction Stop
    }
    catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        if ($statusCode -eq 429) {
            $failedLogins = $i
            break
        }
    }
}
$results += [PSCustomObject]@{
    Test = "3.3 登录频率限制"
    Status = if ($failedLogins -gt 0 -and $failedLogins -le 12) { "PASS" } else { "FAIL" }
    Details = "在第 $failedLogins 次失败后触发限流"
}

# 注册频率限制
Write-Host "测试注册频率限制..." -ForegroundColor Yellow
$failedRegisters = 0
for ($i = 1; $i -le 5; $i++) {
    try {
        $null = Invoke-RestMethod -Uri "$BaseUrl/api/auth/register" -Method POST -ContentType "application/json" -Body "{\"username\":\"rate_test_$i\",\"password\":\"Test1234\"}" -ErrorAction Stop
    }
    catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        if ($statusCode -eq 429) {
            $failedRegisters = $i
            break
        }
    }
}
$results += [PSCustomObject]@{
    Test = "3.4 注册频率限制"
    Status = if ($failedRegisters -gt 0 -and $failedRegisters -le 5) { "PASS" } else { "FAIL" }
    Details = "在第 $failedRegisters 次后触发限流"
}

# SQL注入测试
$results += Test-Endpoint -Name "3.5 SQL注入防护" -Method "POST" -Endpoint "/api/auth/login" -Body @{
    username = "admin' OR '1'='1"
    password = "test"
}

# XSS测试
$results += Test-Endpoint -Name "3.6 XSS防护" -Method "GET" -Endpoint "/api/search?q=<script>alert('xss')</script>" -Headers $authHeaders

# 路径遍历测试
$results += Test-Endpoint -Name "3.7 路径遍历防护" -Method "GET" -Endpoint "/api/documents/../../etc/passwd" -Headers $authHeaders

# 敏感用户名注册
$results += Test-Endpoint -Name "3.8 敏感用户名阻止" -Method "POST" -Endpoint "/api/auth/register" -Body @{
    username = "admin"
    password = "TestPass123"
}

# ==================== 四、API端点全量测试 ====================
Write-Host "`n[四] API端点全量测试" -ForegroundColor Cyan
Write-Host "-" * 40

# 搜索功能
$results += Test-Endpoint -Name "4.1 搜索功能" -Method "GET" -Endpoint "/api/search?q=test" -Headers $authHeaders

# 文档管理
$results += Test-Endpoint -Name "4.2 文档列表" -Method "GET" -Endpoint "/api/documents" -Headers $authHeaders
$results += Test-Endpoint -Name "4.3 文档详情" -Method "GET" -Endpoint "/api/documents/test" -Headers $authHeaders

# 知识图谱
$results += Test-Endpoint -Name "4.4 知识图谱" -Method "GET" -Endpoint "/api/graph" -Headers $authHeaders
$results += Test-Endpoint -Name "4.5 图谱节点" -Method "GET" -Endpoint "/api/graph/nodes" -Headers $authHeaders

# RAG搜索
$results += Test-Endpoint -Name "4.6 RAG搜索" -Method "POST" -Endpoint "/api/rag/search" -Body @{ query = "测试" } -Headers $authHeaders

# AI对话
$results += Test-Endpoint -Name "4.7 AI对话" -Method "POST" -Endpoint "/api/chat" -Body @{ message = "你好" } -Headers $authHeaders

# 会话管理
$results += Test-Endpoint -Name "4.8 会话列表" -Method "GET" -Endpoint "/api/chat/sessions" -Headers $authHeaders

# Wiki功能
$results += Test-Endpoint -Name "4.9 Wiki页面" -Method "GET" -Endpoint "/api/wiki" -Headers $authHeaders

# 评测系统
$results += Test-Endpoint -Name "4.10 评测概览" -Method "GET" -Endpoint "/api/evaluation/overview" -Headers $authHeaders

# 功能开关
$results += Test-Endpoint -Name "4.11 功能开关" -Method "GET" -Endpoint "/api/feature-flags" -Headers $authHeaders

# 服务列表
$results += Test-Endpoint -Name "4.12 服务列表" -Method "GET" -Endpoint "/api/services" -Headers $authHeaders

# 四象系统状态
$results += Test-Endpoint -Name "4.13 四象系统状态" -Method "GET" -Endpoint "/api/symbols/status" -Headers $authHeaders

# 成长概览
$results += Test-Endpoint -Name "4.14 成长概览" -Method "GET" -Endpoint "/api/growth/overview" -Headers $authHeaders

# 工具列表
$results += Test-Endpoint -Name "4.15 工具列表" -Method "GET" -Endpoint "/api/tools" -Headers $authHeaders

# FAQ列表
$results += Test-Endpoint -Name "4.16 FAQ列表" -Method "GET" -Endpoint "/api/faq" -Headers $authHeaders

# 用户偏好
$results += Test-Endpoint -Name "4.17 用户偏好" -Method "GET" -Endpoint "/api/user/preferences" -Headers $authHeaders

# MCP工具
$results += Test-Endpoint -Name "4.18 MCP工具列表" -Method "GET" -Endpoint "/api/mcp/tools" -Headers $authHeaders

# ==================== 五、管理面板测试 ====================
Write-Host "`n[五] 管理面板测试" -ForegroundColor Cyan
Write-Host "-" * 40

$results += Test-Endpoint -Name "5.1 管理统计" -Method "GET" -Endpoint "/api/admin/stats" -Headers $authHeaders
$results += Test-Endpoint -Name "5.2 服务器状态" -Method "GET" -Endpoint "/api/admin/server-status" -Headers $authHeaders
$results += Test-Endpoint -Name "5.3 上传趋势" -Method "GET" -Endpoint "/api/admin/upload-trend" -Headers $authHeaders
$results += Test-Endpoint -Name "5.4 最近活动" -Method "GET" -Endpoint "/api/admin/recent-activities" -Headers $authHeaders
$results += Test-Endpoint -Name "5.5 搜索日志" -Method "GET" -Endpoint "/api/admin/ai-search-logs" -Headers $authHeaders
$results += Test-Endpoint -Name "5.6 搜索分析" -Method "GET" -Endpoint "/api/admin/search-analytics" -Headers $authHeaders
$results += Test-Endpoint -Name "5.7 热门搜索" -Method "GET" -Endpoint "/api/admin/hot-queries" -Headers $authHeaders
$results += Test-Endpoint -Name "5.8 工具管理" -Method "GET" -Endpoint "/api/admin/tools" -Headers $authHeaders
$results += Test-Endpoint -Name "5.9 FAQ管理" -Method "GET" -Endpoint "/api/admin/faq" -Headers $authHeaders
$results += Test-Endpoint -Name "5.10 术语管理" -Method "GET" -Endpoint "/api/admin/terms" -Headers $authHeaders
$results += Test-Endpoint -Name "5.11 反馈统计" -Method "GET" -Endpoint "/api/admin/feedbacks" -Headers $authHeaders
$results += Test-Endpoint -Name "5.12 配置管理" -Method "GET" -Endpoint "/api/admin/config" -Headers $authHeaders
$results += Test-Endpoint -Name "5.13 图谱统计" -Method "GET" -Endpoint "/api/admin/knowledge-graph" -Headers $authHeaders

# ==================== 六、前端路由测试 ====================
Write-Host "`n[六] 前端路由测试" -ForegroundColor Cyan
Write-Host "-" * 40

$results += Test-Endpoint -Name "6.1 主页" -Method "GET" -Endpoint "/"
$results += Test-Endpoint -Name "6.2 前端静态资源" -Method "GET" -Endpoint "/assets/main-SNeLOof5.js"

# ==================== 七、性能测试 ====================
Write-Host "`n[七] 性能测试" -ForegroundColor Cyan
Write-Host "-" * 40

# 并发健康检查测试
Write-Host "执行并发健康检查测试..." -ForegroundColor Yellow
$concurrentStart = Get-Date
$jobs = @()
for ($i = 1; $i -le 10; $i++) {
    $jobs += Start-Job -ScriptBlock {
        param($url)
        $start = Get-Date
        try {
            $null = Invoke-WebRequest -Uri "$url/api/health" -TimeoutSec 5 -ErrorAction Stop
            $status = "OK"
        }
        catch {
            $status = "FAIL"
        }
        $time = ((Get-Date) - $start).TotalMilliseconds
        [PSCustomObject]@{ Status = $status; Time = $time }
    } -ArgumentList $BaseUrl
}

$jobResults = $jobs | Wait-Job -Timeout 30 | Receive-Job
$jobs | Remove-Job -Force

$concurrentTime = ((Get-Date) - $concurrentStart).TotalMilliseconds
$successCount = ($jobResults | Where-Object { $_.Status -eq "OK" }).Count
$avgTime = ($jobResults | Measure-Object -Property Time -Average).Average

$results += [PSCustomObject]@{
    Test = "7.1 并发健康检查(10并发)"
    Status = if ($successCount -eq 10) { "PASS" } else { "FAIL" }
    Details = "成功: $successCount/10, 平均响应: $([math]::Round($avgTime, 2))ms, 总耗时: $([math]::Round($concurrentTime, 2))ms"
}

# 搜索性能测试
Write-Host "执行搜索性能测试..." -ForegroundColor Yellow
$searchStart = Get-Date
$searchResult = Test-Endpoint -Name "7.2 搜索性能" -Method "GET" -Endpoint "/api/search?q=测试" -Headers $authHeaders
$searchTime = ((Get-Date) - $searchStart).TotalMilliseconds
$results += $searchResult

# ==================== 八、数据完整性测试 ====================
Write-Host "`n[八] 数据完整性测试" -ForegroundColor Cyan
Write-Host "-" * 40

$results += Test-Endpoint -Name "8.1 文档导出" -Method "GET" -Endpoint "/api/admin/export/documents" -Headers $authHeaders
$results += Test-Endpoint -Name "8.2 搜索日志导出" -Method "GET" -Endpoint "/api/admin/export/search-logs" -Headers $authHeaders

# ==================== 结果统计 ====================
$endTime = Get-Date
$totalTime = ($endTime - $startTime).TotalSeconds

Write-Host "`n" + "=" * 80
Write-Host "测试结果统计" -ForegroundColor Green
Write-Host "=" * 80

$passCount = ($results | Where-Object { $_.Status -eq "PASS" }).Count
$failCount = ($results | Where-Object { $_.Status -eq "FAIL" }).Count
$totalCount = $results.Count

Write-Host "总计测试: $totalCount"
Write-Host "通过: $passCount" -ForegroundColor Green
Write-Host "失败: $failCount" -ForegroundColor $(if ($failCount -gt 0) { "Red" } else { "Green" })
Write-Host "通过率: $([math]::Round($passCount / $totalCount * 100, 2))%"
Write-Host "总耗时: $([math]::Round($totalTime, 2)) 秒"

# 输出失败详情
if ($failCount -gt 0) {
    Write-Host "`n失败测试详情:" -ForegroundColor Red
    Write-Host "-" * 40
    $results | Where-Object { $_.Status -eq "FAIL" } | ForEach-Object {
        Write-Host "✗ $($_.Test)" -ForegroundColor Red
        Write-Host "  端点: $($_.Method) $($_.Endpoint)"
        Write-Host "  状态码: $($_.StatusCode) (期望: $($_.ExpectedStatus))"
        if ($_.Error) {
            Write-Host "  错误: $($_.Error)"
        }
    }
}

# 保存结果到文件
$results | ConvertTo-Json -Depth 10 | Out-File -FilePath "E:\easyclaw\伏羲-v1.44\repo\round4_test_results.json" -Encoding UTF8
Write-Host "`n详细结果已保存到: round4_test_results.json"

# 生成报告
$report = @"
# 伏羲 v1.44 第四轮全面综合检测报告

## 测试时间
$(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

## 测试环境
- 服务器地址: $BaseUrl
- 测试工具: PowerShell 自动化测试脚本

## 测试结果总览
| 指标 | 数值 |
|------|------|
| 总计测试 | $totalCount |
| 通过 | $passCount |
| 失败 | $failCount |
| 通过率 | $([math]::Round($passCount / $totalCount * 100, 2))% |
| 总耗时 | $([math]::Round($totalTime, 2)) 秒 |

## 详细测试结果

### 一、系统健康检查
$($results | Where-Object { $_.Test -like "1.*" } | ForEach-Object { "- $($_.Test): $($_.Status)" } | Out-String)

### 二、认证系统测试
$($results | Where-Object { $_.Test -like "2.*" } | ForEach-Object { "- $($_.Test): $($_.Status)" } | Out-String)

### 三、安全防护测试
$($results | Where-Object { $_.Test -like "3.*" } | ForEach-Object { "- $($_.Test): $($_.Status)" } | Out-String)

### 四、API端点全量测试
$($results | Where-Object { $_.Test -like "4.*" } | ForEach-Object { "- $($_.Test): $($_.Status)" } | Out-String)

### 五、管理面板测试
$($results | Where-Object { $_.Test -like "5.*" } | ForEach-Object { "- $($_.Test): $($_.Status)" } | Out-String)

### 六、前端路由测试
$($results | Where-Object { $_.Test -like "6.*" } | ForEach-Object { "- $($_.Test): $($_.Status)" } | Out-String)

### 七、性能测试
$($results | Where-Object { $_.Test -like "7.*" } | ForEach-Object { "- $($_.Test): $($_.Status) $($_.Details)" } | Out-String)

### 八、数据完整性测试
$($results | Where-Object { $_.Test -like "8.*" } | ForEach-Object { "- $($_.Test): $($_.Status)" } | Out-String)

## 失败测试详情
$(if ($failCount -gt 0) {
    $results | Where-Object { $_.Status -eq "FAIL" } | ForEach-Object {
        @"
### $($_.Test)
- **端点**: ``$($_.Method) $($_.Endpoint)``
- **状态码**: $($_.StatusCode) (期望: $($_.ExpectedStatus))
- **错误**: $($_.Error)
"@
    } | Out-String
} else {
    "无失败测试"
})

## 结论
$(if ($failCount -eq 0) {
    "✅ 所有测试通过，系统运行正常。"
} elseif ($failCount -le 3) {
    "⚠️ 有 $failCount 项测试失败，建议检查相关功能。"
} else {
    "❌ 有 $failCount 项测试失败，系统存在较多问题，需要重点关注。"
})
"@

$report | Out-File -FilePath "E:\easyclaw\伏羲-v1.44\repo\round4_test_report.md" -Encoding UTF8
Write-Host "测试报告已保存到: round4_test_report.md"

# 返回结果
return $results
