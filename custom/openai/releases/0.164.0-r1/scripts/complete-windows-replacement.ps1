$ErrorActionPreference = 'Stop'
$taskBin = [IO.Path]::GetFullPath('C:\Users\qiopgh\.codex\bin')
$taskReceipt = Join-Path $PSScriptRoot 'windows-deployment.json'
$taskRecord = Get-Content -Raw -LiteralPath $taskReceipt | ConvertFrom-Json
if ($taskRecord.version -ne '0.164.0' -or $taskRecord.destination -ne $taskBin) { throw '部署记录不符合本次替换范围' }
if (-not (Test-Path -LiteralPath $taskRecord.backup_directory)) { throw '原程序备份目录不存在' }

# 必须先完全退出 App；本脚本不会关闭任何进程。
$taskBusy = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
Get-CimInstance Win32_Process | ForEach-Object {
    if ($_.ExecutablePath) { [void]$taskBusy.Add([IO.Path]::GetFullPath($_.ExecutablePath)) }
}
foreach ($taskRename in $taskRecord.pending_renames) {
    $taskFrom = [IO.Path]::GetFullPath($taskRename.from)
    $taskTo = [IO.Path]::GetFullPath($taskRename.to)
    if (-not $taskFrom.StartsWith($taskBin + '\', [StringComparison]::OrdinalIgnoreCase) -or
        -not $taskTo.StartsWith($taskBin + '\', [StringComparison]::OrdinalIgnoreCase) -or
        -not $taskFrom.EndsWith('.new.exe', [StringComparison]::OrdinalIgnoreCase)) { throw '替换路径超出授权目录' }
    if ($taskBusy.Contains($taskFrom) -or $taskBusy.Contains($taskTo)) { throw ('请先完全退出 App，程序仍被占用：' + $taskTo) }
    $taskEntry = $taskRecord.files | Where-Object { $_.deployed_file -eq $taskRename.from } | Select-Object -First 1
    if (-not $taskEntry) { throw '找不到文件校验记录' }
    if (-not (Test-Path -LiteralPath $taskFrom)) {
        if ((Get-FileHash -LiteralPath $taskTo -Algorithm SHA256).Hash.ToLowerInvariant() -eq $taskEntry.sha256) { continue }
        throw ('新文件不存在且正式文件不匹配：' + $taskFrom)
    }
    if ((Get-FileHash -LiteralPath $taskFrom -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskEntry.sha256) { throw ('新文件校验失败：' + $taskFrom) }
}
foreach ($taskRename in $taskRecord.pending_renames) {
    if (Test-Path -LiteralPath $taskRename.from) {
        Move-Item -LiteralPath $taskRename.from -Destination $taskRename.to -Force
    }
}
foreach ($taskEntry in $taskRecord.files) {
    if ((Get-FileHash -LiteralPath $taskEntry.target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskEntry.sha256) { throw ('正式文件校验失败：' + $taskEntry.target) }
}
$taskVersion = & (Join-Path $taskBin 'codex.exe') --version
if ($LASTEXITCODE -ne 0 -or $taskVersion -ne 'codex-cli 0.164.0') { throw '正式入口版本验证失败' }
[ordered]@{ completed_at = (Get-Date).ToString('o'); version = $taskVersion; verified_files = $taskRecord.files.Count; app_restarted = $false } |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'windows-manual-replacement.json') -Encoding utf8
Write-Output '正式程序已替换并核对为 codex-cli 0.164.0。请重新启动 App 后测试界面和实际问答。'
