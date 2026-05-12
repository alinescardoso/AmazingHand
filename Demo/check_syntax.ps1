$errs = $null
$null = [System.Management.Automation.Language.Parser]::ParseFile(
    "$PSScriptRoot\install_windows_real_demo.ps1",
    [ref]$null,
    [ref]$errs
)
if ($errs.Count -eq 0) {
    Write-Host "Sem erros de sintaxe." -ForegroundColor Green
} else {
    foreach ($e in $errs) { Write-Host $e.ToString() -ForegroundColor Red }
}
