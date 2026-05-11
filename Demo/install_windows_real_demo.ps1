param(
    [int]$CameraIndex = -1,
    [string]$ComPort = "",
    [string]$DemoFile = "",
    [string]$PythonVersion = "3.12",
    [switch]$SkipRun,
    [switch]$NonInteractive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-CommandExists {
    param([Parameter(Mandatory = $true)][string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Add-ToSessionPathIfExists {
    param([Parameter(Mandatory = $true)][string]$PathToAdd)
    if (Test-Path $PathToAdd) {
        if (($env:Path -split ';') -notcontains $PathToAdd) {
            $env:Path = "$PathToAdd;$env:Path"
        }
    }
}

function Ensure-WingetPackage {
    param(
        [Parameter(Mandatory = $true)][string]$CommandName,
        [Parameter(Mandatory = $true)][string]$WingetId,
        [Parameter(Mandatory = $true)][string]$DisplayName
    )

    if (Test-CommandExists $CommandName) {
        Write-Host "[OK] $DisplayName ja esta instalado."
        return
    }

    if (-not (Test-CommandExists "winget")) {
        throw "winget nao encontrado. Instale o App Installer da Microsoft Store."
    }

    Write-Host "[INFO] Instalando $DisplayName via winget ($WingetId)..."
    winget install --id $WingetId -e --accept-source-agreements --accept-package-agreements

    if (-not (Test-CommandExists $CommandName)) {
        throw "Falha ao instalar $DisplayName. Abra um novo terminal e rode novamente este script."
    }
}

function Ensure-DoraCli {
    Add-ToSessionPathIfExists "$env:USERPROFILE\.local\bin"
    Add-ToSessionPathIfExists "$env:APPDATA\Python\Python312\Scripts"

    if (Test-CommandExists "dora") {
        Write-Host "[OK] dora-rs-cli ja esta instalado."
        return
    }

    Write-Host "[INFO] Instalando dora-rs-cli..."
    if (Test-CommandExists "uv") {
        uv tool install --force dora-rs-cli
        Add-ToSessionPathIfExists "$env:USERPROFILE\.local\bin"
    }

    if (-not (Test-CommandExists "dora")) {
        if (Test-CommandExists "python") {
            python -m pip install --user dora-rs-cli
            Add-ToSessionPathIfExists "$env:APPDATA\Python\Python312\Scripts"
        }
    }

    if (-not (Test-CommandExists "dora")) {
        throw "Nao foi possivel instalar o dora-rs-cli automaticamente."
    }
}

function Ensure-PythonRuntime {
    param([Parameter(Mandatory = $true)][string]$Version)

    if (Test-CommandExists "python") {
        Write-Host "[OK] Python ja esta instalado."
        return
    }

    Write-Host "[INFO] Python nao encontrado. Tentando instalar com uv python install $Version..."
    try {
        uv python install $Version
    }
    catch {
        Write-Warning "Falha ao instalar Python com uv. Tentando winget..."
    }

    if (-not (Test-CommandExists "python")) {
        Ensure-WingetPackage -CommandName "python" -WingetId "Python.Python.3.12" -DisplayName "Python 3.12"
    }

    if (-not (Test-CommandExists "python")) {
        throw "Python nao foi encontrado apos as tentativas de instalacao."
    }
}

function Ensure-UvCli {
    if (Test-CommandExists "uv") {
        Write-Host "[OK] uv ja esta instalado."
        return
    }

    Ensure-WingetPackage -CommandName "uv" -WingetId "astral-sh.uv" -DisplayName "uv"

    if (Test-CommandExists "uv") {
        return
    }

    if (Test-CommandExists "python") {
        Write-Warning "uv nao ficou disponivel via winget nesta sessao. Tentando via pip --user..."
        python -m pip install --user uv
        Add-ToSessionPathIfExists "$env:APPDATA\Python\Python312\Scripts"
    }

    if (-not (Test-CommandExists "uv")) {
        throw "Nao foi possivel disponibilizar o comando uv automaticamente."
    }
}

function Sync-UvProject {
    param([Parameter(Mandatory = $true)][string]$ProjectPath)

    $pyproject = Join-Path $ProjectPath "pyproject.toml"
    if (-not (Test-Path $pyproject)) {
        return
    }

    Write-Host "[INFO] Sincronizando dependencias com uv sync em $ProjectPath"
    Push-Location $ProjectPath
    try {
        uv sync
    }
    finally {
        Pop-Location
    }
}

function Update-DataflowComPort {
    param(
        [Parameter(Mandatory = $true)][string]$DataflowPath,
        [Parameter(Mandatory = $true)][string]$ComPortValue
    )

    $content = Get-Content -Raw -Path $DataflowPath
    $updated = $content -replace '--serialport\s+\S+', "--serialport $ComPortValue"

    if ($updated -ne $content) {
        Set-Content -Path $DataflowPath -Value $updated -Encoding UTF8
        Write-Host "[OK] Porta serial atualizada em $([System.IO.Path]::GetFileName($DataflowPath)): $ComPortValue"
    }
    else {
        Write-Warning "Nao foi encontrado '--serialport ...' em $DataflowPath."
    }
}

function Get-AvailableComPorts {
    $ports = @()
    try {
        $ports = @(Get-CimInstance Win32_SerialPort |
            Sort-Object DeviceID |
            ForEach-Object {
                [PSCustomObject]@{
                    Id = $_.DeviceID
                    Label = "$($_.DeviceID) - $($_.Name)"
                }
            })
    }
    catch {
        Write-Warning "Nao foi possivel listar portas COM automaticamente."
    }
    return @($ports)
}

function Get-AvailableCameras {
    $cameras = @()
    try {
        $cameras = @(Get-CimInstance Win32_PnPEntity |
            Where-Object {
                ($_.PNPClass -eq "Camera" -or $_.PNPClass -eq "Image") -and
                $_.Status -eq "OK"
            } |
            Sort-Object Name |
            Select-Object -ExpandProperty Name)
    }
    catch {
        Write-Warning "Nao foi possivel listar cameras automaticamente."
    }
    return @($cameras)
}

function Select-FromList {
    param(
        [Parameter(Mandatory = $true)][string]$Title,
        [Parameter(Mandatory = $true)]$Items,
        [string]$Default = ""
    )

    $Items = @($Items)

    Write-Host ""
    Write-Host "[SELECAO] $Title"
    for ($i = 0; $i -lt $Items.Count; $i++) {
        Write-Host ("[{0}] {1}" -f ($i + 1), $Items[$i])
    }

    $defaultText = ""
    if ($Default) {
        $defaultText = " (Enter usa: $Default)"
    }

    while ($true) {
        $answer = Read-Host "Digite o numero$defaultText"
        if ([string]::IsNullOrWhiteSpace($answer) -and $Default) {
            return $Default
        }

        $parsed = 0
        if ([int]::TryParse($answer, [ref]$parsed) -and $parsed -ge 1 -and $parsed -le $Items.Count) {
            return $Items[$parsed - 1]
        }

        Write-Warning "Opcao invalida."
    }
}

function Select-CameraIndex {
    param([switch]$NonInteractiveMode)

    $cameras = @(Get-AvailableCameras)
    if ($cameras.Count -gt 0) {
        Write-Host "[INFO] Cameras detectadas no Windows:"
        for ($i = 0; $i -lt $cameras.Count; $i++) {
            Write-Host ("  - {0}" -f $cameras[$i])
        }
        Write-Host "[INFO] O indice OpenCV (0, 1, 2...) pode nao seguir exatamente esta ordem."
    }
    else {
        Write-Warning "Nenhuma camera detectada automaticamente."
    }

    if ($NonInteractiveMode) {
        return 0
    }

    while ($true) {
        $answer = Read-Host "Escolha o indice da camera para OpenCV (0/1/2...). Enter usa 0"
        if ([string]::IsNullOrWhiteSpace($answer)) {
            return 0
        }
        $idx = 0
        if ([int]::TryParse($answer, [ref]$idx) -and $idx -ge 0) {
            return $idx
        }
        Write-Warning "Indice invalido."
    }
}

function Resolve-DemoFile {
    param(
        [string]$RequestedDemo,
        [switch]$NonInteractiveMode
    )

    $available = @(Get-ChildItem -Path . -Filter "dataflow_*.yml" -File |
        Sort-Object Name |
        Select-Object -ExpandProperty Name)

    if ($available.Count -eq 0) {
        throw "Nenhum dataflow_*.yml encontrado na pasta Demo."
    }

    if ($RequestedDemo) {
        if ($available -contains $RequestedDemo) {
            return $RequestedDemo
        }
        throw "Demo '$RequestedDemo' nao encontrada. Disponiveis: $($available -join ', ')"
    }

    if ($NonInteractiveMode) {
        if ($available -contains "dataflow_tracking_real.yml") {
            return "dataflow_tracking_real.yml"
        }
        return $available[0]
    }

    return Select-FromList -Title "Escolha o demo/dataflow" -Items $available -Default "dataflow_tracking_real.yml"
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $scriptDir

try {
    $selectedDemo = Resolve-DemoFile -RequestedDemo $DemoFile -NonInteractiveMode:$NonInteractive

    $selectedDemoPath = Join-Path $scriptDir $selectedDemo
    $selectedDemoContent = Get-Content -Raw -Path $selectedDemoPath
    $needsComPort = $selectedDemoContent -match '--serialport\s+'
    $usesHandTracking = $selectedDemoContent -match 'HandTracking/HandTracking/main.py|hand_tracker'

    if ($needsComPort -and [string]::IsNullOrWhiteSpace($ComPort)) {
        $ports = @(Get-AvailableComPorts)
        if ($ports.Count -gt 0 -and -not $NonInteractive) {
            $labels = @($ports | Select-Object -ExpandProperty Label)
            $selectedLabel = Select-FromList -Title "Escolha a porta COM" -Items $labels -Default $labels[0]
            $ComPort = ($ports | Where-Object { $_.Label -eq $selectedLabel } | Select-Object -First 1).Id
        }
        elseif ($ports.Count -gt 0 -and $NonInteractive) {
            $ComPort = $ports[0].Id
        }
        elseif ($NonInteractive) {
            $ComPort = "COM3"
        }
        else {
            $ComPort = Read-Host "Digite a porta COM manualmente (ex: COM3)"
        }
    }

    if ($usesHandTracking -and $CameraIndex -lt 0) {
        $CameraIndex = Select-CameraIndex -NonInteractiveMode:$NonInteractive
    }
    elseif ($CameraIndex -lt 0) {
        $CameraIndex = 0
    }

    Write-Host "[INFO] Preparando ambiente para demo=$selectedDemo camera=$CameraIndex porta=$ComPort"

    Ensure-WingetPackage -CommandName "rustup" -WingetId "Rustlang.Rustup" -DisplayName "Rust"
    Ensure-UvCli

    Add-ToSessionPathIfExists "$env:USERPROFILE\.cargo\bin"
    Add-ToSessionPathIfExists "$env:USERPROFILE\.local\bin"

    Ensure-PythonRuntime -Version $PythonVersion
    Ensure-DoraCli

    $venvPython = Join-Path $scriptDir ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        Write-Host "[OK] Ambiente virtual ja existe em .venv (reutilizando)."
    }
    else {
        Write-Host "[INFO] Criando ambiente virtual Python ($PythonVersion)..."
        uv venv --python $PythonVersion
    }

    Sync-UvProject -ProjectPath (Join-Path $scriptDir "HandTracking")
    Sync-UvProject -ProjectPath (Join-Path $scriptDir "AHSimulation")

    if ($needsComPort) {
        if ([string]::IsNullOrWhiteSpace($ComPort)) {
            throw "A demo selecionada requer porta COM, mas nenhuma foi definida."
        }
        Update-DataflowComPort -DataflowPath $selectedDemoPath -ComPortValue $ComPort
    }

    $env:AH_CAMERA_INDEX = "$CameraIndex"
    Write-Host "[OK] AH_CAMERA_INDEX definido para $env:AH_CAMERA_INDEX"

    Write-Host "[INFO] Subindo daemon do dora (dora up)..."
    try {
        Start-Process -FilePath "dora" -ArgumentList "up" -WindowStyle Hidden | Out-Null
    }
    catch {
        Write-Warning "Nao foi possivel iniciar dora up em background. Tentando no processo atual."
        dora up
    }

    Write-Host "[INFO] Build do fluxo: $selectedDemo"
    dora build $selectedDemo --uv

    if (-not $SkipRun) {
        Write-Host "[INFO] Executando fluxo: $selectedDemo"
        dora run $selectedDemo --uv
    }
    else {
        Write-Host "[OK] Build concluido. Execucao pulada por -SkipRun."
    }
}
finally {
    Pop-Location
}
