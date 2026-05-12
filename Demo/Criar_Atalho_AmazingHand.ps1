param(
    [string]$ShortcutName = "AmazingHand Demo"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcher = Join-Path $scriptDir "Abrir_AmazingHand_Demo.cmd"

if (-not (Test-Path $launcher)) {
    Write-Error "Launcher nao encontrado: $launcher"
    exit 1
}

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop ("{0}.lnk" -f $ShortcutName)

$wsh = New-Object -ComObject WScript.Shell
$sc = $wsh.CreateShortcut($shortcutPath)
$sc.TargetPath = $launcher
$sc.WorkingDirectory = $scriptDir
$sc.IconLocation = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe,0"
$sc.Description = "Inicia o install_windows_real_demo.ps1"
$sc.Save()

Write-Host "Atalho criado: $shortcutPath"
