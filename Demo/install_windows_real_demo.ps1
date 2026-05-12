param(
    [int]$CameraIndex = 0,
    [string]$ComPort = "COM3",
    [string]$DemoFile = "dataflow_tracking_real.yml",
    [string]$PythonVersion = "3.12",
    [switch]$SkipRun,
    [switch]$NonInteractive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-CommandExists {
    param([Parameter(Mandatory)][string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Add-ToSessionPathIfExists {
    param([Parameter(Mandatory)][string]$PathToAdd)
    if ((Test-Path $PathToAdd) -and (($env:Path -split ';') -notcontains $PathToAdd)) {
        $env:Path = "$PathToAdd;$env:Path"
    }
}

function Ensure-WingetPackage {
    param(
        [Parameter(Mandatory)][string]$CommandName,
        [Parameter(Mandatory)][string]$WingetId,
        [Parameter(Mandatory)][string]$DisplayName
    )

    if (Test-CommandExists $CommandName) {
        Write-Host "[OK] $DisplayName ja instalado."
        return
    }

    if (-not (Test-CommandExists "winget")) {
        throw "winget nao encontrado. Instale o App Installer da Microsoft Store."
    }

    Write-Host "[..] Instalando $DisplayName via winget..."
    winget install --id $WingetId -e --accept-source-agreements --accept-package-agreements

    if (-not (Test-CommandExists $CommandName)) {
        throw "Falha ao instalar $DisplayName. Abra um novo terminal e rode novamente."
    }
}

function Ensure-UvCli {
    if (Test-CommandExists "uv") {
        Write-Host "[OK] uv ja instalado."
        return
    }

    Ensure-WingetPackage -CommandName "uv" -WingetId "astral-sh.uv" -DisplayName "uv"

    Add-ToSessionPathIfExists "$env:USERPROFILE\.local\bin"
    Add-ToSessionPathIfExists "$env:APPDATA\Python\Python312\Scripts"

    if (-not (Test-CommandExists "uv") -and (Test-CommandExists "python")) {
        Write-Host "[!] uv nao entrou no PATH da sessao. Tentando via pip --user..."
        python -m pip install --user uv
        Add-ToSessionPathIfExists "$env:APPDATA\Python\Python312\Scripts"
    }

    if (-not (Test-CommandExists "uv")) {
        throw "Nao foi possivel disponibilizar o comando uv automaticamente."
    }
}

function Ensure-PythonRuntime {
    param([Parameter(Mandatory)][string]$Version)

    if (Test-CommandExists "python") {
        Write-Host "[OK] Python ja instalado."
        return
    }

    Write-Host "[..] Python nao encontrado. Tentando instalar com uv python install $Version..."
    try {
        uv python install $Version
    }
    catch {
        Write-Host "[!] Falha com uv python install. Tentando winget..."
    }

    if (-not (Test-CommandExists "python")) {
        Ensure-WingetPackage -CommandName "python" -WingetId "Python.Python.3.12" -DisplayName "Python 3.12"
    }

    if (-not (Test-CommandExists "python")) {
        throw "Python nao foi encontrado apos as tentativas de instalacao."
    }
}

function Ensure-DoraCli {
    Add-ToSessionPathIfExists "$env:USERPROFILE\.local\bin"
    Add-ToSessionPathIfExists "$env:APPDATA\Python\Python312\Scripts"

    if (Test-CommandExists "dora") {
        Write-Host "[OK] dora-rs-cli ja instalado."
        return
    }

    Write-Host "[..] Instalando dora-rs-cli..."
    if (Test-CommandExists "uv") {
        uv tool install --force dora-rs-cli
        Add-ToSessionPathIfExists "$env:USERPROFILE\.local\bin"
    }

    if (-not (Test-CommandExists "dora") -and (Test-CommandExists "python")) {
        python -m pip install --user dora-rs-cli
        Add-ToSessionPathIfExists "$env:APPDATA\Python\Python312\Scripts"
    }

    if (-not (Test-CommandExists "dora")) {
        throw "Nao foi possivel instalar dora-rs-cli automaticamente."
    }
}

function Sync-UvProject {
    param([Parameter(Mandatory)][string]$ProjectPath)

    $pyproject = Join-Path $ProjectPath "pyproject.toml"
    if (-not (Test-Path $pyproject)) {
        return
    }

    Write-Host "[..] uv sync em $ProjectPath"
    Push-Location $ProjectPath
    try {
        uv sync
    }
    finally {
        Pop-Location
    }
}

function Get-AvailableComPorts {
    try {
        return @(Get-CimInstance Win32_SerialPort |
            Sort-Object DeviceID |
            ForEach-Object {
                [PSCustomObject]@{ Id = $_.DeviceID; Name = $_.Name }
            })
    }
    catch {
        return @()
    }
}

function Get-AvailableCameras {
    try {
        return @(Get-CimInstance Win32_PnPEntity |
            Where-Object { ($_.PNPClass -eq "Camera" -or $_.PNPClass -eq "Image") -and $_.Status -eq "OK" } |
            Sort-Object Name |
            Select-Object -ExpandProperty Name)
    }
    catch {
        return @()
    }
}

function Update-DataflowComPort {
    param(
        [Parameter(Mandatory)][string]$DataflowPath,
        [Parameter(Mandatory)][string]$ComPortValue
    )

    $content = Get-Content -Raw -Path $DataflowPath
    $updated = $content -replace '--serialport\s+\S+', "--serialport $ComPortValue"

    if ($updated -ne $content) {
        Set-Content -Path $DataflowPath -Value $updated -Encoding UTF8
        Write-Host "[OK] COM atualizada em $([System.IO.Path]::GetFileName($DataflowPath)): $ComPortValue"
    }
}

function Show-InstallerGui {
    param(
        [Parameter(Mandatory)][string[]]$AvailableDemos,
        [object[]]$ComPorts = @(),
        [string[]]$Cameras = @(),
        [Parameter(Mandatory)][string]$DefaultDemo,
        [Parameter(Mandatory)][string]$DefaultCom,
        [Parameter(Mandatory)][int]$DefaultCamera,
        [Parameter(Mandatory)][bool]$DefaultSkipRun
    )

    $ComPorts = @($ComPorts)
    $Cameras = @($Cameras)

    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing

    $form = New-Object System.Windows.Forms.Form
    $form.Text = "Amazing Hand Installer"
    $form.Size = New-Object System.Drawing.Size(620, 360)
    $form.StartPosition = "CenterScreen"
    $form.FormBorderStyle = "FixedDialog"
    $form.MaximizeBox = $false

    $title = New-Object System.Windows.Forms.Label
    $title.Text = "Configuracao do Demo"
    $title.Font = New-Object System.Drawing.Font("Segoe UI", 14, [System.Drawing.FontStyle]::Bold)
    $title.Location = New-Object System.Drawing.Point(20, 15)
    $title.Size = New-Object System.Drawing.Size(300, 30)

    $lblDemo = New-Object System.Windows.Forms.Label
    $lblDemo.Text = "Demo (dataflow):"
    $lblDemo.Location = New-Object System.Drawing.Point(20, 65)
    $lblDemo.Size = New-Object System.Drawing.Size(130, 20)

    $cmbDemo = New-Object System.Windows.Forms.ComboBox
    $cmbDemo.Location = New-Object System.Drawing.Point(160, 62)
    $cmbDemo.Size = New-Object System.Drawing.Size(420, 25)
    $cmbDemo.DropDownStyle = "DropDownList"
    [void]$cmbDemo.Items.AddRange($AvailableDemos)
    $idxDemo = [Array]::IndexOf($AvailableDemos, $DefaultDemo)
    $cmbDemo.SelectedIndex = $(if ($idxDemo -ge 0) { $idxDemo } else { 0 })

    $lblCom = New-Object System.Windows.Forms.Label
    $lblCom.Text = "Porta COM:"
    $lblCom.Location = New-Object System.Drawing.Point(20, 110)
    $lblCom.Size = New-Object System.Drawing.Size(130, 20)

    $cmbCom = New-Object System.Windows.Forms.ComboBox
    $cmbCom.Location = New-Object System.Drawing.Point(160, 107)
    $cmbCom.Size = New-Object System.Drawing.Size(420, 25)
    $cmbCom.DropDownStyle = "DropDown"

    foreach ($p in $ComPorts) {
        [void]$cmbCom.Items.Add("$($p.Id) - $($p.Name)")
    }
    $cmbCom.Text = $DefaultCom

    $lblCam = New-Object System.Windows.Forms.Label
    $lblCam.Text = "Camera (indice OpenCV):"
    $lblCam.Location = New-Object System.Drawing.Point(20, 155)
    $lblCam.Size = New-Object System.Drawing.Size(130, 35)

    $cmbCam = New-Object System.Windows.Forms.ComboBox
    $cmbCam.Location = New-Object System.Drawing.Point(160, 155)
    $cmbCam.Size = New-Object System.Drawing.Size(420, 25)
    $cmbCam.DropDownStyle = "DropDownList"

    $maxIdx = [Math]::Max(3, $Cameras.Count - 1)
    for ($i = 0; $i -le $maxIdx; $i++) {
        $name = if ($i -lt $Cameras.Count) { $Cameras[$i] } else { "nao detectada" }
        [void]$cmbCam.Items.Add("$i - $name")
    }
    $cmbCam.SelectedIndex = [Math]::Max(0, [Math]::Min($DefaultCamera, $cmbCam.Items.Count - 1))

    $chkSkip = New-Object System.Windows.Forms.CheckBox
    $chkSkip.Text = "Apenas build (nao executar dora run)"
    $chkSkip.Location = New-Object System.Drawing.Point(20, 205)
    $chkSkip.Size = New-Object System.Drawing.Size(320, 25)
    $chkSkip.Checked = $DefaultSkipRun

    $hint = New-Object System.Windows.Forms.Label
    $hint.Text = "Layout em execucao: MuJoCo na parte de baixo e camera no canto superior direito."
    $hint.Location = New-Object System.Drawing.Point(20, 235)
    $hint.Size = New-Object System.Drawing.Size(560, 35)

    $btnRun = New-Object System.Windows.Forms.Button
    $btnRun.Text = "Instalar e Executar"
    $btnRun.Location = New-Object System.Drawing.Point(330, 275)
    $btnRun.Size = New-Object System.Drawing.Size(120, 30)
    $btnRun.DialogResult = [System.Windows.Forms.DialogResult]::OK

    $btnCancel = New-Object System.Windows.Forms.Button
    $btnCancel.Text = "Cancelar"
    $btnCancel.Location = New-Object System.Drawing.Point(460, 275)
    $btnCancel.Size = New-Object System.Drawing.Size(120, 30)
    $btnCancel.DialogResult = [System.Windows.Forms.DialogResult]::Cancel

    $form.Controls.AddRange(@($title, $lblDemo, $cmbDemo, $lblCom, $cmbCom, $lblCam, $cmbCam, $chkSkip, $hint, $btnRun, $btnCancel))

    $form.AcceptButton = $btnRun
    $form.CancelButton = $btnCancel

    $dialog = $form.ShowDialog()
    if ($dialog -ne [System.Windows.Forms.DialogResult]::OK) {
        return $null
    }

    $selectedDemo = $cmbDemo.SelectedItem
    if ($null -eq $selectedDemo) {
        $selectedDemo = $DefaultDemo
    }

    $comText = $cmbCom.Text.Trim()
    if ($comText -match "^(COM\d+)") {
        $comText = $Matches[1]
    }
    elseif ($comText -match "^COM\d+$") {
        $comText = $comText
    }
    elseif (-not [string]::IsNullOrWhiteSpace($comText)) {
        $comText = $comText.Split(' ')[0]
    }

    $selectedCam = $cmbCam.SelectedItem
    if ($null -eq $selectedCam) {
        $camIndex = $DefaultCamera
    }
    else {
        $camIndex = [int]($selectedCam.ToString().Split('-')[0].Trim())
    }

    return [PSCustomObject]@{
        DemoFile = $selectedDemo.ToString()
        ComPort = $(if ([string]::IsNullOrWhiteSpace($comText)) { $DefaultCom } else { $comText })
        CameraIndex = $camIndex
        SkipRun = $chkSkip.Checked
    }
}

function Start-WindowArrangerJob {
    param(
        [bool]$HasMujoco,
        [bool]$HasCamera
    )

    $job = Start-Job -ArgumentList $HasMujoco, $HasCamera -ScriptBlock {
        param($JobHasMujoco, $JobHasCamera)

        Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
using System.Collections.Generic;
public class AHWinAPI {
    [DllImport("user32.dll")]
    public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndAfter, int X, int Y, int cx, int cy, uint uFlags);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWinCb lpEnumFunc, IntPtr lParam);
    public delegate bool EnumWinCb(IntPtr hWnd, IntPtr lParam);
    public static List<IntPtr> Find(string partial) {
        var list = new List<IntPtr>();
        EnumWindows((hWnd, lParam) => {
            if (!IsWindowVisible(hWnd)) return true;
            var sb = new StringBuilder(256);
            GetWindowText(hWnd, sb, 256);
            if (sb.ToString().IndexOf(partial, StringComparison.OrdinalIgnoreCase) >= 0) {
                list.Add(hWnd);
            }
            return true;
        }, IntPtr.Zero);
        return list;
    }
}
'@ -ErrorAction SilentlyContinue

        Add-Type -AssemblyName System.Windows.Forms
        $wa = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea

        $camW = [int]($wa.Width * 0.34)
        $camH = [int]($wa.Height * 0.34)
        $camX = $wa.Left + $wa.Width - $camW
        $camY = $wa.Top

        $mujX = $wa.Left
        $mujY = $wa.Top + $camH
        $mujW = $wa.Width
        $mujH = $wa.Height - $camH

        $placedMuj = -not $JobHasMujoco
        $placedCam = -not $JobHasCamera

        for ($iter = 0; $iter -lt 140; $iter++) {
            Start-Sleep -Milliseconds 500

            if (-not $placedMuj) {
                $mw = [AHWinAPI]::Find("MuJoCo")
                if ($mw.Count -eq 0) { $mw = [AHWinAPI]::Find("mujoco viewer") }
                if ($mw.Count -gt 0) {
                    [AHWinAPI]::ShowWindow($mw[0], 9) | Out-Null
                    [AHWinAPI]::SetWindowPos($mw[0], [IntPtr]::Zero, $mujX, $mujY, $mujW, $mujH, 0x0040) | Out-Null
                    $placedMuj = $true
                }
            }

            if (-not $placedCam) {
                $cw = [AHWinAPI]::Find("MediaPipe Hands")
                if ($cw.Count -gt 0) {
                    [AHWinAPI]::ShowWindow($cw[0], 9) | Out-Null
                    [AHWinAPI]::SetWindowPos($cw[0], [IntPtr]::Zero, $camX, $camY, $camW, $camH, 0x0040) | Out-Null
                    $placedCam = $true
                }
            }

            if ($placedMuj -and $placedCam) {
                break
            }
        }
    }

    return $job
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $scriptDir

try {
    $availableDemos = @(Get-ChildItem -Path . -Filter "dataflow_*.yml" -File |
        Sort-Object Name |
        Select-Object -ExpandProperty Name)

    if ($availableDemos.Count -eq 0) {
        throw "Nenhum dataflow_*.yml encontrado na pasta Demo."
    }

    if (-not ($availableDemos -contains $DemoFile)) {
        $DemoFile = "dataflow_tracking_real.yml"
    }
    if (-not ($availableDemos -contains $DemoFile)) {
        $DemoFile = $availableDemos[0]
    }

    if (-not $NonInteractive) {
        $detectedComPorts = @(Get-AvailableComPorts)
        $detectedCameras = @(Get-AvailableCameras)

        $selection = Show-InstallerGui `
            -AvailableDemos $availableDemos `
            -ComPorts $detectedComPorts `
            -Cameras $detectedCameras `
            -DefaultDemo $DemoFile `
            -DefaultCom $ComPort `
            -DefaultCamera $CameraIndex `
            -DefaultSkipRun ([bool]$SkipRun)

        if ($null -eq $selection) {
            Write-Host "[!] Cancelado pelo usuario."
            return
        }

        $DemoFile = $selection.DemoFile
        $ComPort = $selection.ComPort
        $CameraIndex = $selection.CameraIndex
        $SkipRun = [bool]$selection.SkipRun
    }

    $selectedDemoPath = Join-Path $scriptDir $DemoFile
    $selectedDemoContent = Get-Content -Raw -Path $selectedDemoPath
    $needsComPort = $selectedDemoContent -match '--serialport\s+'
    $usesHandTracking = $selectedDemoContent -match 'HandTracking/HandTracking/main.py|hand_tracker'
    $usesMuJoCo = $selectedDemoContent -match 'AHSimulation|mj_mink'

    Write-Host "[..] Preparando demo=$DemoFile camera=$CameraIndex COM=$ComPort"

    Ensure-WingetPackage -CommandName "rustup" -WingetId "Rustlang.Rustup" -DisplayName "Rust"
    Ensure-UvCli

    Add-ToSessionPathIfExists "$env:USERPROFILE\.cargo\bin"
    Add-ToSessionPathIfExists "$env:USERPROFILE\.local\bin"

    Ensure-PythonRuntime -Version $PythonVersion
    Ensure-DoraCli

    $venvPython = Join-Path $scriptDir ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        Write-Host "[OK] .venv ja existe (reutilizando)."
    }
    else {
        Write-Host "[..] Criando .venv com Python $PythonVersion..."
        uv venv --python $PythonVersion
    }

    Sync-UvProject -ProjectPath (Join-Path $scriptDir "HandTracking")
    Sync-UvProject -ProjectPath (Join-Path $scriptDir "AHSimulation")

    if ($needsComPort) {
        Update-DataflowComPort -DataflowPath $selectedDemoPath -ComPortValue $ComPort
    }

    $env:AH_CAMERA_INDEX = "$CameraIndex"
    Write-Host "[OK] AH_CAMERA_INDEX=$env:AH_CAMERA_INDEX"

    Write-Host "[..] Iniciando dora daemon..."
    try {
        Start-Process -FilePath "dora" -ArgumentList "up" -WindowStyle Hidden | Out-Null
        Start-Sleep -Seconds 2
    }
    catch {
        Write-Host "[!] Start-Process falhou; tentando dora up direto."
        dora up
    }

    Write-Host "[..] Build: $DemoFile"
    dora build $DemoFile --uv

    if ($SkipRun) {
        Write-Host "[OK] -SkipRun ativo: build concluido, sem executar."
        return
    }

    $arrangerJob = Start-WindowArrangerJob -HasMujoco $usesMuJoCo -HasCamera $usesHandTracking

    Write-Host "[..] Run: $DemoFile"
    dora run $DemoFile --uv

    if ($null -ne $arrangerJob) {
        Wait-Job $arrangerJob -Timeout 5 | Out-Null
        Remove-Job $arrangerJob -Force | Out-Null
    }
}
finally {
    Pop-Location
}
