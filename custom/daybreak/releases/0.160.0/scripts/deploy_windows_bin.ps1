$ErrorActionPreference = 'Stop'

$taskWorkspace = 'C:\Users\qiopgh\Documents\Codex\2026-10-01\codex-cli-windows-linux-x86-64'
$taskHome = 'C:\Users\qiopgh\.codex'
$taskBin = [IO.Path]::GetFullPath((Join-Path $taskHome 'bin'))
$taskDelivery = 'C:\Users\qiopgh\Documents\Codex\2026-10-01\codex-cli-windows-linux-x86-64\outputs\codex-0.160.0'
$taskSource = Join-Path $taskDelivery 'codex-0.160.0-openai-daybreak-r1-windows-x86_64'
$taskPython = 'C:\Users\qiopgh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$taskStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$taskBackup = Join-Path $taskHome ('backups\cli-before-0.160.0-' + $taskStamp)
$taskRecordPath = Join-Path $taskDelivery 'windows-deployment.json'
$taskConfigPath = Join-Path $taskHome 'config.toml'
$taskConfigHash = (Get-FileHash -LiteralPath $taskConfigPath -Algorithm SHA256).Hash
$taskReadConfigState = 'import hashlib,json,sys,tomllib; from pathlib import Path; p=Path(sys.argv[1]); c=tomllib.loads(p.read_text(encoding="utf-8")); m=Path(c["model_catalog_json"]) if c.get("model_catalog_json") else None; v=c.get("model_providers",{}).get("openai",{}); print(json.dumps({"config_sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"catalog_path":str(m) if m else None,"catalog_sha256":hashlib.sha256(m.read_bytes()).hexdigest() if m else None,"daybreak_compat_enabled":v.get("experimental_daybreak_app_compat",False),"daybreak_compat_explicit":"experimental_daybreak_app_compat" in v}))'
$taskConfigState = (& $taskPython -X utf8 -c $taskReadConfigState $taskConfigPath) | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw '配置及模型目录状态读取失败' }
$taskPreviousVersion = & (Join-Path $taskBin 'codex.exe') --version
if ($LASTEXITCODE -ne 0) { throw '旧程序版本读取失败' }
$taskBuild = Get-Content -LiteralPath (Join-Path $taskSource 'custom-build.json') -Raw | ConvertFrom-Json

if ($taskBin -ne 'C:\Users\qiopgh\.codex\bin') { throw '部署目标不符合预期' }
if (Test-Path -LiteralPath $taskRecordPath) { throw '已有同版部署记录，需要先核对再继续' }

# 先核对完整交付包，随后才改动安装目录。
foreach ($taskEntry in $taskBuild.files) {
    $taskFile = Join-Path $taskSource $taskEntry.path
    if ((Get-FileHash -LiteralPath $taskFile -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskEntry.sha256) {
        throw ('源文件校验失败：' + $taskEntry.path)
    }
}
$taskBusyPaths = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
Get-CimInstance Win32_Process | ForEach-Object {
    if ($_.ExecutablePath) { [void]$taskBusyPaths.Add([IO.Path]::GetFullPath($_.ExecutablePath)) }
}

New-Item -ItemType Directory -Path $taskBackup | Out-Null
Copy-Item -LiteralPath $taskBin -Destination (Join-Path $taskBackup 'bin') -Recurse
Copy-Item -LiteralPath $taskConfigPath -Destination (Join-Path $taskBackup 'config.toml')
if ($taskConfigState.catalog_path) { Copy-Item -LiteralPath $taskConfigState.catalog_path -Destination (Join-Path $taskBackup 'model-catalog.json') }
& $taskPython -X utf8 (Join-Path $taskWorkspace 'work\update-0.160.0\backup_windows_cli_databases.py') $taskHome (Join-Path $taskBackup 'databases')
if ($LASTEXITCODE -ne 0) { throw '数据库备份失败，部署已停止' }

$taskRecord = [ordered]@{
    started_at = (Get-Date).ToString('o')
    version = '0.160.0'
    destination = $taskBin
    backup_directory = $taskBackup
    previous_cli_path = [Environment]::GetEnvironmentVariable('CODEX_CLI_PATH', 'User')
    previous_version = $taskPreviousVersion
    catalog_sha256_before = $taskConfigState.catalog_sha256
    daybreak_compat_enabled = $taskConfigState.daybreak_compat_enabled
    daybreak_compat_explicit = $taskConfigState.daybreak_compat_explicit
    config_sha256_before = $taskConfigHash.ToLowerInvariant()
    files = [Collections.Generic.List[object]]::new()
    pending_renames = [Collections.Generic.List[object]]::new()
    status = 'copying'
}
$taskRecord | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $taskBackup 'deployment.json') -Encoding utf8NoBOM

function Install-TaskFile {
    param([string]$SourceFile, [string]$RelativePath, [string]$ExpectedHash)
    $taskTarget = [IO.Path]::GetFullPath((Join-Path $taskBin $RelativePath))
    if (-not $taskTarget.StartsWith($taskBin + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw '文件目标超出 bin 目录'
    }
    $taskActual = $taskTarget
    $taskPending = $false
    if ($taskBusyPaths.Contains($taskTarget)) {
        if ([IO.Path]::GetExtension($taskTarget) -ne '.exe') { throw ('文件被占用：' + $taskTarget) }
        $taskActual = Join-Path ([IO.Path]::GetDirectoryName($taskTarget)) ([IO.Path]::GetFileNameWithoutExtension($taskTarget) + '.new.exe')
        $taskPending = $true
    }
    if ($taskBusyPaths.Contains($taskActual)) { throw ('暂存名称也被占用：' + $taskActual) }
    New-Item -ItemType Directory -Force -Path ([IO.Path]::GetDirectoryName($taskActual)) | Out-Null
    try {
        Copy-Item -LiteralPath $SourceFile -Destination $taskActual -Force
    } catch {
        if ($taskPending -or [IO.Path]::GetExtension($taskTarget) -ne '.exe') { throw }
        $taskActual = Join-Path ([IO.Path]::GetDirectoryName($taskTarget)) ([IO.Path]::GetFileNameWithoutExtension($taskTarget) + '.new.exe')
        if ($taskBusyPaths.Contains($taskActual)) { throw }
        Copy-Item -LiteralPath $SourceFile -Destination $taskActual -Force
        $taskPending = $true
    }
    $taskHash = (Get-FileHash -LiteralPath $taskActual -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($taskHash -ne $ExpectedHash) { throw ('部署文件校验失败：' + $taskActual) }
    $taskRecord.files.Add([ordered]@{ target = $taskTarget; deployed_file = $taskActual; sha256 = $taskHash; pending_rename = $taskPending })
    if ($taskPending) { $taskRecord.pending_renames.Add([ordered]@{ from = $taskActual; to = $taskTarget }) }
}

foreach ($taskEntry in $taskBuild.files) {
    if ($taskEntry.path -eq 'codex-package.json') { continue }
    $taskRelative = $taskEntry.path
    if ($taskRelative.StartsWith('bin/')) { $taskRelative = $taskRelative.Substring(4) }
    Install-TaskFile (Join-Path $taskSource $taskEntry.path) $taskRelative $taskEntry.sha256
}

# 保留原先同目录沙箱程序的调用方式；资源目录中的同版副本也完整部署。
foreach ($taskName in @('codex-command-runner.exe', 'codex-windows-sandbox-setup.exe', 'codex-windows-sandbox-service.exe')) {
    $taskEntry = $taskBuild.files | Where-Object { $_.path -eq ('codex-resources/' + $taskName) }
    Install-TaskFile (Join-Path $taskSource $taskEntry.path) $taskName $taskEntry.sha256
}

# 新版支持 Windows 根目录入口布局，元数据必须准确指向同目录 codex.exe。
$taskLayout = Get-Content -LiteralPath (Join-Path $taskSource 'codex-package.json') -Raw | ConvertFrom-Json
$taskLayout.entrypoint = 'codex.exe'
$taskLayout | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $taskBin 'codex-package.json') -Encoding utf8NoBOM
Copy-Item -LiteralPath (Join-Path $taskSource 'custom-build.json') -Destination (Join-Path $taskBackup 'new-package-build.json')
Copy-Item -LiteralPath (Join-Path $taskSource 'custom-build.json') -Destination (Join-Path $taskBin 'custom-build.json')

$taskMain = $taskRecord.files | Where-Object { $_.target -eq (Join-Path $taskBin 'codex.exe') } | Select-Object -First 1
$taskVersion = & $taskMain.deployed_file --version
if ($LASTEXITCODE -ne 0 -or $taskVersion -ne 'codex-cli 0.160.0') { throw '新主程序版本验证失败' }
if ((Get-FileHash -LiteralPath $taskConfigPath -Algorithm SHA256).Hash -ne $taskConfigHash) { throw '配置文件在部署期间发生了变化，需要核对' }
$taskConfigStateAfter = (& $taskPython -X utf8 -c $taskReadConfigState $taskConfigPath) | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $taskConfigStateAfter.catalog_sha256 -ne $taskConfigState.catalog_sha256) { throw '模型目录在部署期间发生了变化，需要核对' }

$taskExpectedCli = Join-Path $taskBin 'codex.exe'
if ([Environment]::GetEnvironmentVariable('CODEX_CLI_PATH', 'User') -ne $taskExpectedCli) {
    [Environment]::SetEnvironmentVariable('CODEX_CLI_PATH', $taskExpectedCli, 'User')
}
$taskRecord.status = if ($taskRecord.pending_renames.Count) { 'awaiting_manual_renames' } else { 'deployed_restart_required' }
$taskRecord.version_output = $taskVersion
$taskRecord.cli_path = [Environment]::GetEnvironmentVariable('CODEX_CLI_PATH', 'User')
$taskRecord.config_sha256_after = $taskConfigHash.ToLowerInvariant()
$taskRecord.catalog_sha256_after = $taskConfigStateAfter.catalog_sha256
$taskRecord.catalog_unchanged = $true
$taskRecord.package_layout_sha256 = (Get-FileHash -LiteralPath (Join-Path $taskBin 'codex-package.json') -Algorithm SHA256).Hash.ToLowerInvariant()
$taskRecord.completed_at = (Get-Date).ToString('o')
$taskRecord | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskRecordPath -Encoding utf8NoBOM
$taskRecord | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $taskBackup 'deployment.json') -Encoding utf8NoBOM
[ordered]@{ status = $taskRecord.status; version = $taskVersion; destination = $taskBin; verified_files = $taskRecord.files.Count; pending_renames = $taskRecord.pending_renames; backup_directory = $taskBackup; cli_path = $taskRecord.cli_path; config_unchanged = $true } | ConvertTo-Json -Depth 6
