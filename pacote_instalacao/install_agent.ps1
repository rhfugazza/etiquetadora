param(
  [string]$ApiBaseUrl = "https://disparo-etiquetadora.di6lja.easypanel.host",
  [string]$ApiKey = "ROTATIVA-PRINT-2025",
  [string]$AgentId = $env:COMPUTERNAME,
  [string]$InstallDir = "$env:LOCALAPPDATA\\Rotativa\\Etiquetadora",
  [switch]$SkipAutoStart
)

$ErrorActionPreference = "Stop"

function Write-Info($msg) {
  Write-Host "[INFO] $msg" -ForegroundColor Cyan
}

function Write-Warn($msg) {
  Write-Host "[WARN] $msg" -ForegroundColor Yellow
}

function Write-Err($msg) {
  Write-Host "[ERRO] $msg" -ForegroundColor Red
}

function Ensure-Tls12 {
  try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  } catch {
    # ignore
  }
}

function Ensure-Python {
  $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
  if ($pythonCmd) {
    return $pythonCmd.Source
  }

  $pyCmd = Get-Command py -ErrorAction SilentlyContinue
  if ($pyCmd) {
    return "py"
  }

  $winget = Get-Command winget -ErrorAction SilentlyContinue
  if (-not $winget) {
    Write-Err "winget nao encontrado. Instale o App Installer da Microsoft Store e rode novamente."
    exit 1
  }

  Write-Info "Instalando Python 3.12 via winget..."
  winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements

  $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
  if ($pythonCmd) {
    return $pythonCmd.Source
  }

  $pyCmd = Get-Command py -ErrorAction SilentlyContinue
  if ($pyCmd) {
    return "py"
  }

  Write-Err "Python nao encontrado apos instalacao."
  exit 1
}

function Pip-Install($pythonExe, $package) {
  Write-Info "Instalando $package..."
  if ($pythonExe -eq "py") {
    py -3 -m pip install --no-warn-script-location --upgrade $package
  } else {
    & $pythonExe -m pip install --no-warn-script-location --upgrade $package
  }
}

function Download-File($url, $outFile) {
  Write-Info "Baixando $url"
  Invoke-WebRequest -Uri $url -OutFile $outFile
}

Ensure-Tls12

$pythonExe = Ensure-Python

Pip-Install $pythonExe "pip"
Pip-Install $pythonExe "pywin32"

if (-not (Test-Path $InstallDir)) {
  Write-Info "Criando pasta $InstallDir"
  New-Item -ItemType Directory -Path $InstallDir | Out-Null
}

$repoOwner = "rhfugazza"
$repoName = "etiquetadora"
$branch = "main"
$rawBase = "https://raw.githubusercontent.com/$repoOwner/$repoName/$branch"

Download-File "$rawBase/print_agent.py" (Join-Path $InstallDir "print_agent.py")
Download-File "$rawBase/imprimir_lote.py" (Join-Path $InstallDir "imprimir_lote.py")
Download-File "$rawBase/start_agent.bat" (Join-Path $InstallDir "start_agent.bat")

$cfg = @{
  api_base_url = $ApiBaseUrl
  api_key = $ApiKey
  agent_id = $AgentId
  poll_seconds = 5
  request_timeout_seconds = 15
}
$cfg | ConvertTo-Json -Depth 3 | Set-Content -Encoding UTF8 (Join-Path $InstallDir "agent_config.json")

if (-not $SkipAutoStart) {
  $taskName = "RotativaEtiquetadoraAgent"
  $taskCmd = "`"$pythonExe`" `"$InstallDir\\print_agent.py`""

  Write-Info "Criando tarefa de inicializacao ($taskName)"
  schtasks /Create /TN $taskName /TR $taskCmd /SC ONLOGON /F | Out-Null
}

Write-Info "Instalacao concluida."
Write-Info "Pasta: $InstallDir"
Write-Info "Para testar agora:"
Write-Host "  `"$pythonExe`" `"$InstallDir\\print_agent.py`"" -ForegroundColor Green
