$baseUrl="http://172.25.30.200:8080"
$adminToken = Get-Content "$PSScriptRoot\admin_token.txt"
$userToken = Get-Content "$PSScriptRoot\user_token.txt"

# ====== H-01: JWT Expiry ======
Write-Host "========== H-01: JWT Token Expiry =========="
$payload = $userToken.Split('.')[1]
$payload = $payload.PadRight($payload.Length + (4 - $payload.Length % 4) % 4, '=')
$decoded = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($payload))
Write-Host "User token payload: $decoded"
$json = $decoded | ConvertFrom-Json
$iat = [DateTimeOffset]::FromUnixTimeSeconds($json.iat).LocalDateTime
$exp = [DateTimeOffset]::FromUnixTimeSeconds($json.exp).LocalDateTime
$ttl = $json.exp - $json.iat
Write-Host "iat: $iat"
Write-Host "exp: $exp"
Write-Host "TTL: $ttl seconds ($([Math]::Round($ttl/3600,1)) hours)"
$ttlOk = ($ttl -le 7200) -and ($ttl -gt 0)
Write-Host "TTL <= 2 hours: $ttlOk"

# ====== H-02: Rate Limit ======
Write-Host ""
Write-Host "========== H-02: Rate Limit DoS =========="
$rateLimitHit = $false
for ($i=1; $i -le 12; $i++) {
  try {
    $regBody = @{username="recheck_rl_$(Get-Random -Minimum 10000 -Maximum 99999)"; password="Abc12345"; display_name="RL Test"} | ConvertTo-Json
    $resp = Invoke-RestMethod -Uri "$baseUrl/api/auth/register" -Method Post -ContentType "application/json" -Body $regBody
    Write-Host "  Registration ${i}: SUCCESS"
  } catch {
    $sc = $_.Exception.Response.StatusCode.value__
    Write-Host "  Registration ${i}: $sc"
    if ($sc -eq 429) {
      $rateLimitHit = $true
      Write-Host "  Rate limit hit at attempt $i"
      break
    }
  }
}
Write-Host "Rate limit triggered: $rateLimitHit"

# ====== H-03: Password Complexity ======
Write-Host ""
Write-Host "========== H-03: Password Complexity =========="

$tests = @(
  @{pw="123456"; desc="too short, digits only"; expected="reject"},
  @{pw="12345678"; desc="8 chars, no uppercase"; expected="reject"},
  @{pw="abcdefgh"; desc="8 chars, lowercase only"; expected="reject"},
  @{pw="Abcdefgh"; desc="8 chars, no digit"; expected="reject"},
  @{pw="Abcdefg1"; desc="8 chars, upper+lower+digit"; expected="accept"}
)

foreach ($test in $tests) {
  $regBody = @{username="pwtest_$(Get-Random -Minimum 10000 -Maximum 99999)"; password=$test.pw; display_name="PW Test"} | ConvertTo-Json
  try {
    $resp = Invoke-RestMethod -Uri "$baseUrl/api/auth/register" -Method Post -ContentType "application/json" -Body $regBody
    $pass = if ($test.expected -eq "accept") { "PASS" } else { "FAIL" }
    Write-Host "  '$($test.pw)' ($($test.desc)): ACCEPTED - $pass"
  } catch {
    $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
    $body = $reader.ReadToEnd()
    $pass = if ($test.expected -eq "reject") { "PASS" } else { "FAIL" }
    Write-Host "  '$($test.pw)' ($($test.desc)): REJECTED ($body) - $pass"
  }
}

Write-Host ""
Write-Host "========== TESTS COMPLETE =========="
