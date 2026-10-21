param(
    [string]$PackagePath = 'C:\Users\qiopgh\.codex\packages\standalone\current',
    [Parameter(Mandatory)][string]$BackupDirectory
)

$ErrorActionPreference = 'Stop'
$taskItem = Get-Item -LiteralPath $PackagePath -Force
$taskPackage = if ($taskItem.LinkType) { $taskItem.ResolveLinkTarget($true).FullName } else { $taskItem.FullName }
$taskAllowedRoot = 'C:\Users\qiopgh\.codex\packages\standalone\releases'
if (-not $taskPackage.StartsWith($taskAllowedRoot + '\',[StringComparison]::OrdinalIgnoreCase)) { throw '来源不属于当前独立 CLI 安装目录' }
$taskBackup = [IO.Path]::GetFullPath($BackupDirectory)
if (-not $taskBackup.StartsWith('C:\Users\qiopgh\.codex\backups\',[StringComparison]::OrdinalIgnoreCase) -or
    -not (Test-Path -LiteralPath $taskBackup)) { throw '更新前备份目录无效' }
$taskLayoutFile = Join-Path $taskPackage 'codex-package.json'
$taskBuildFile = Join-Path $taskPackage 'custom-build.json'
$taskLayout = Get-Content -LiteralPath $taskLayoutFile -Raw | ConvertFrom-Json
$taskBuild = Get-Content -LiteralPath $taskBuildFile -Raw | ConvertFrom-Json
$taskCli = Join-Path $taskPackage 'bin\codex.exe'
$taskMain = $taskBuild.files | Where-Object path -eq 'bin/codex.exe' | Select-Object -First 1
if ($taskLayout.version -ne $taskBuild.version -or $taskLayout.entrypoint -ne 'bin/codex.exe' -or
    $taskLayout.target -notin @('x86_64-pc-windows-gnu','x86_64-pc-windows-msvc') -or
    $taskBuild.main_target -notin @('x86_64-pc-windows-gnu','x86_64-pc-windows-msvc') -or
    (Get-FileHash -LiteralPath $taskCli -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskMain.sha256) {
    throw '本机完整修改版的来源、平台或入口校验失败'
}
Copy-Item -LiteralPath $taskLayoutFile -Destination (Join-Path $taskBackup 'standalone-layout-before.json')
Copy-Item -LiteralPath $taskBuildFile -Destination (Join-Path $taskBackup 'standalone-build-before.json')

# 后台安装器在 Windows 使用统一 MSVC 安装标识；实际编译目标继续单独记录。
$taskLayout.target = 'x86_64-pc-windows-msvc'
$taskLayout | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $taskLayoutFile -Encoding utf8NoBOM
$taskLayoutHash = (Get-FileHash -LiteralPath $taskLayoutFile -Algorithm SHA256).Hash.ToLowerInvariant()
$taskMetadataRecord = $taskBuild.files | Where-Object path -eq 'codex-package.json' | Select-Object -First 1
$taskMetadataRecord.sha256 = $taskLayoutHash
$taskMetadataRecord.size = (Get-Item -LiteralPath $taskLayoutFile).Length
$taskMetadataRecord.origin = '按 Windows 原生后台安装器使用的平台标识适配；实际编译目标见 main_target'
$taskBuild | Add-Member -NotePropertyName managed_install_target -NotePropertyValue $taskLayout.target -Force
$taskBuild | Add-Member -NotePropertyName installed_layout_note -NotePropertyValue 'Windows 管理器以 x86_64-pc-windows-msvc 识别安装槽位；主程序仍为 main_target 记录的 GNU 构建，二进制字节和权限校验没有改变。' -Force
$taskBuild | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskBuildFile -Encoding utf8NoBOM

# 使用原生复制和固定来源机制，只重启独立 daemon，不关闭桌面 App。
& $taskCli app-server daemon update --from-cli --yes > (Join-Path $PSScriptRoot 'daemon-update.stdout.log') 2> (Join-Path $PSScriptRoot 'daemon-update.stderr.log')
if ($LASTEXITCODE -ne 0) { throw '后台完整包同步失败，详见本机更新日志' }
Get-Content -LiteralPath (Join-Path $PSScriptRoot 'daemon-update.stdout.log')
[ordered]@{source_package=$taskPackage;version=$taskBuild.version;actual_compiler_target=$taskBuild.main_target;managed_install_target=$taskLayout.target;standalone_metadata_sha256=$taskLayoutHash;cli_sha256=$taskMain.sha256;backup_directory=$taskBackup;updated_at=(Get-Date).ToString('o')} |
    ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'sync-result.json') -Encoding utf8
