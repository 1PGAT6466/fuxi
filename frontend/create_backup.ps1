# Create backup directory
$backupDir = "backup_$(Get-Date -Format 'yyyyMMdd')"
New-Item -ItemType Directory -Path $backupDir -Force

# Copy files to backup
Copy-Item -Path "css", "js", "login.html", "index.html" -Destination $backupDir -Recurse -Force

Write-Host "Backup created in $backupDir"