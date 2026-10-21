param(
    [Parameter(Mandatory)][string]$PackagePath,
    [Parameter(Mandatory)][string]$RecordPath
)

$ErrorActionPreference = 'Stop'
$taskHome = 'C:\Users\qiopgh\.codex'
$taskPathEntry = 'C:\Users\qiopgh\AppData\Local\Programs\OpenAI\Codex\bin'
$taskCurrent = Join-Path $taskHome 'packages\standalone\current'
$taskSource = [IO.Path]::GetFullPath($PackagePath)
$taskBuild = Get-Content -LiteralPath (Join-Path $taskSource 'custom-build.json') -Raw | ConvertFrom-Json
$taskCurrentItem = Get-Item -LiteralPath $taskCurrent -Force
$taskPathItem = Get-Item -LiteralPath $taskPathEntry -Force
$taskPackage = $taskCurrentItem.ResolveLinkTarget($true).FullName
$taskResolvedBin = $taskPathItem.ResolveLinkTarget($true).FullName
$taskReleaseRoot = [IO.Path]::GetFullPath((Join-Path $taskHome 'packages\standalone\releases'))
if (-not $taskPackage.StartsWith($taskReleaseRoot + '\', [StringComparison]::OrdinalIgnoreCase) -or
    $taskResolvedBin -ine (Join-Path $taskPackage 'bin')) { throw '原 PATH 入口没有连接到预期的 standalone 安装目录' }
$taskOriginalLayout = Get-Content -LiteralPath (Join-Path $taskPackage 'codex-package.json') -Raw | ConvertFrom-Json
if ($taskOriginalLayout.version -ne $taskBuild.version -or $taskOriginalLayout.entrypoint -ne 'bin/codex.exe') {
    throw '当前 standalone 包的版本或布局与交付包不匹配'
}
$taskUserPathBefore = [Environment]::GetEnvironmentVariable('Path','User')
$taskAppPathBefore = [Environment]::GetEnvironmentVariable('CODEX_CLI_PATH','User')
$taskAppFilesBefore = @('codex.exe','codex-code-mode-host.exe') | ForEach-Object {
    $taskFile = Join-Path $taskHome ('bin\' + $_)
    [ordered]@{path=$taskFile;sha256=(Get-FileHash -LiteralPath $taskFile -Algorithm SHA256).Hash.ToLowerInvariant()}
}
$taskAutoUpdateFile = Join-Path $taskHome 'packages\standalone\auto-update-version'
$taskAutoUpdateBefore = (Get-FileHash -LiteralPath $taskAutoUpdateFile -Algorithm SHA256).Hash

# 写入前核对完整交付包，备份原独立安装包和当前环境。
foreach ($taskEntry in $taskBuild.files) {
    $taskSourceFile = [IO.Path]::GetFullPath((Join-Path $taskSource $taskEntry.path))
    if (-not $taskSourceFile.StartsWith($taskSource + '\', [StringComparison]::OrdinalIgnoreCase) -or
        (Get-FileHash -LiteralPath $taskSourceFile -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskEntry.sha256) {
        throw ('交付文件校验失败：' + $taskEntry.path)
    }
}
$taskBackup = Join-Path $taskHome ('backups\standalone-cli-before-' + $taskBuild.version + '-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $taskBackup | Out-Null
Copy-Item -LiteralPath $taskPackage -Destination (Join-Path $taskBackup 'package') -Recurse
$taskEnvironment = [ordered]@{saved_at=(Get-Date).ToString('o');user_path=$taskUserPathBefore;user_CODEX_CLI_PATH=$taskAppPathBefore;path_entry=$taskPathEntry;path_junction_target=$taskPathItem.Target;current_junction_target=$taskCurrentItem.Target;resolved_package=$taskPackage;app_files=$taskAppFilesBefore;auto_update_version_sha256=$taskAutoUpdateBefore}
$taskEnvironment | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $taskBackup 'environment-before.json') -Encoding utf8
$taskPython = 'C:\Users\qiopgh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $taskPython -X utf8 'work\update-0.163.0\backup_windows_cli_databases.py' $taskHome (Join-Path $taskBackup 'databases')
if ($LASTEXITCODE -ne 0) { throw '数据库一致性备份失败' }

$taskBusyPaths = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
Get-CimInstance Win32_Process | ForEach-Object {
    if ($_.ExecutablePath) { [void]$taskBusyPaths.Add([IO.Path]::GetFullPath($_.ExecutablePath)) }
}
$taskFiles = [Collections.Generic.List[object]]::new()
$taskPending = [Collections.Generic.List[object]]::new()
foreach ($taskEntry in $taskBuild.files) {
    $taskTarget = [IO.Path]::GetFullPath((Join-Path $taskPackage $taskEntry.path))
    if (-not $taskTarget.StartsWith($taskPackage + '\', [StringComparison]::OrdinalIgnoreCase)) { throw '文件写入路径超出独立安装目录' }
    $taskExistingHash = if (Test-Path -LiteralPath $taskTarget) { (Get-FileHash -LiteralPath $taskTarget -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
    $taskActual = $taskTarget
    $taskDisposition = 'already_matches'
    if ($taskExistingHash -ne $taskEntry.sha256) {
        if ($taskBusyPaths.Contains($taskTarget)) {
            if ([IO.Path]::GetExtension($taskTarget) -ine '.exe') { throw ('非程序文件被占用：' + $taskTarget) }
            $taskActual = Join-Path ([IO.Path]::GetDirectoryName($taskTarget)) ([IO.Path]::GetFileNameWithoutExtension($taskTarget) + '.new.exe')
        }
        if ($taskBusyPaths.Contains($taskActual)) { throw ('暂存程序也被占用：' + $taskActual) }
        New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($taskActual)) -Force | Out-Null
        try {
            Copy-Item -LiteralPath (Join-Path $taskSource $taskEntry.path) -Destination $taskActual -Force
        } catch {
            if ($taskActual -ne $taskTarget -or [IO.Path]::GetExtension($taskTarget) -ine '.exe') { throw }
            $taskActual = Join-Path ([IO.Path]::GetDirectoryName($taskTarget)) ([IO.Path]::GetFileNameWithoutExtension($taskTarget) + '.new.exe')
            if ($taskBusyPaths.Contains($taskActual)) { throw }
            Copy-Item -LiteralPath (Join-Path $taskSource $taskEntry.path) -Destination $taskActual -Force
        }
        $taskDisposition = if ($taskActual -eq $taskTarget) { 'replaced' } else { 'staged' }
    }
    if ((Get-FileHash -LiteralPath $taskActual -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskEntry.sha256) { throw ('安装后文件校验失败：' + $taskActual) }
    $taskFiles.Add([ordered]@{relative_path=$taskEntry.path;target=$taskTarget;deployed_file=$taskActual;sha256=$taskEntry.sha256;disposition=$taskDisposition})
    if ($taskActual -ne $taskTarget) { $taskPending.Add([ordered]@{from=$taskActual;to=$taskTarget}) }
}
Copy-Item -LiteralPath (Join-Path $taskSource 'custom-build.json') -Destination (Join-Path $taskPackage 'custom-build.json') -Force

# 保留当前用户 PATH、原独立 CLI 连接和 App 覆写入口。
if ([Environment]::GetEnvironmentVariable('Path','User') -ne $taskUserPathBefore) { throw '用户 PATH 在部署期间发生变化，需要核对' }
if ((Get-Item -LiteralPath $taskCurrent -Force).Target -ne $taskCurrentItem.Target -or
    (Get-Item -LiteralPath $taskPathEntry -Force).Target -ne $taskPathItem.Target -or
    (Get-FileHash -LiteralPath $taskAutoUpdateFile -Algorithm SHA256).Hash -ne $taskAutoUpdateBefore) { throw '原独立更新布局发生了意外变化' }
if ([Environment]::GetEnvironmentVariable('CODEX_CLI_PATH','User') -ne $taskAppPathBefore) { throw 'App 覆写入口发生了意外变化' }
foreach ($taskAppFile in $taskAppFilesBefore) {
    if ((Get-FileHash -LiteralPath $taskAppFile.path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskAppFile.sha256) { throw ('App 程序发生了意外变化：' + $taskAppFile.path) }
}
$taskMain = $taskFiles | Where-Object relative_path -eq 'bin/codex.exe' | Select-Object -First 1
$taskVersion = & $taskMain.deployed_file --version
if ($LASTEXITCODE -ne 0 -or $taskVersion -ne ('codex-cli ' + $taskBuild.version)) { throw '独立修改版版本检查失败' }
$taskRecord = [ordered]@{completed_at=(Get-Date).ToString('o');status=$(if ($taskPending.Count) {'awaiting_manual_renames'} else {'deployed'});version=$taskVersion;path_entry=(Join-Path $taskPathEntry 'codex.exe');resolved_package=$taskPackage;backup_directory=$taskBackup;user_path=[Environment]::GetEnvironmentVariable('Path','User');app_CODEX_CLI_PATH=$taskAppPathBefore;app_binaries_unchanged=$true;standalone_junctions_unchanged=$true;auto_update_version_unchanged=$true;files=@($taskFiles);pending_renames=@($taskPending)}
$taskRecord | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $RecordPath -Encoding utf8
$taskRecord | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $taskBackup 'deployment.json') -Encoding utf8
[ordered]@{status=$taskRecord.status;version=$taskVersion;path_entry=$taskRecord.path_entry;resolved_package=$taskPackage;verified_files=$taskFiles.Count;replaced_files=@($taskFiles | Where-Object disposition -eq 'replaced').Count;pending_renames=@($taskPending);backup_directory=$taskBackup;user_path=$taskRecord.user_path;app_binaries_unchanged=$true;standalone_junctions_unchanged=$true;auto_update_version_unchanged=$true} | ConvertTo-Json -Depth 4
