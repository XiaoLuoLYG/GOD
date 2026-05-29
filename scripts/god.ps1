#requires -Version 5.1
param(
  [Parameter(Position = 0)]
  [string]$Action = "menu"
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
  throw "scripts/god.ps1 is for native Windows PowerShell. Use ./scripts/god.sh on macOS/Linux."
}

function Join-PathMany {
  param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Parts)
  if ($Parts.Count -eq 0) {
    return ""
  }
  $path = $Parts[0]
  for ($i = 1; $i -lt $Parts.Count; $i++) {
    $path = Join-Path $path $Parts[$i]
  }
  return $path
}

function Write-GodLog {
  param([string]$Message)
  Write-Host "[GOD] $Message"
}

function Write-GodDiagnostic {
  param([AllowNull()][string]$Message)
  [Console]::Error.WriteLine($Message)
}

function Stop-God {
  param([string]$Message)
  throw "[GOD] error: $Message"
}

function Test-CommandExists {
  param([string]$Name)
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-ToolPath {
  param([string[]]$Names)
  foreach ($name in $Names) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) {
      return $cmd.Source
    }
  }
  return $Names[0]
}

function Quote-PSLiteral {
  param([AllowNull()][string]$Value)
  if ($null -eq $Value) {
    return "''"
  }
  return "'" + $Value.Replace("'", "''") + "'"
}

function Write-TextUtf8NoBom {
  param(
    [string]$Path,
    [string]$Content
  )
  $parent = Split-Path -Parent $Path
  if ($parent) {
    [System.IO.Directory]::CreateDirectory($parent) | Out-Null
  }
  $encoding = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

$script:RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$script:EnvFile = if ($env:GOD_ENV_FILE) { $env:GOD_ENV_FILE } else { Join-Path $script:RootDir ".env" }

$script:InitialEnv = @{
  GOD_EXPERIMENT = $env:GOD_EXPERIMENT
  GOD_EXPERIMENT_RUN = $env:GOD_EXPERIMENT_RUN
  GOD_HYPOTHESIS_ID = $env:GOD_HYPOTHESIS_ID
  GOD_EXPERIMENT_ID = $env:GOD_EXPERIMENT_ID
  LIVE_WORKSPACE_PATH = $env:LIVE_WORKSPACE_PATH
  GOD_MAP_ID = $env:GOD_MAP_ID
}

$script:StateDir = Join-Path $script:RootDir ".god"
$script:LogDir = Join-Path $script:StateDir "logs"
$script:PidDir = Join-Path $script:StateDir "pids"
$script:RunDir = Join-Path $script:StateDir "run"
New-Item -ItemType Directory -Force -Path $script:LogDir, $script:PidDir, $script:RunDir | Out-Null

$script:BackendPidFile = Join-Path $script:PidDir "backend.pid"
$script:FrontendPidFile = Join-Path $script:PidDir "frontend.pid"
$script:RuntimePidFile = Join-Path $script:PidDir "runtime.pid"
$script:CurrentExperimentFile = Join-Path $script:StateDir "current_experiment.json"
$script:StartRequestFile = Join-Path $script:RunDir "start-request.json"

$script:BackendLog = Join-Path $script:LogDir "backend.log"
$script:FrontendLog = Join-Path $script:LogDir "frontend.log"
$script:RuntimeLog = Join-Path $script:LogDir "runtime.log"
$script:RuntimeInitLog = Join-Path $script:LogDir "runtime-init.log"

function Get-EnvValue {
  param(
    [string]$Name,
    [string]$Default = ""
  )
  $value = [System.Environment]::GetEnvironmentVariable($Name, "Process")
  if ([string]::IsNullOrEmpty($value)) {
    return $Default
  }
  return $value
}

function Set-ProcessEnv {
  param(
    [string]$Name,
    [AllowNull()][string]$Value
  )
  [System.Environment]::SetEnvironmentVariable($Name, $Value, "Process")
}

function Remove-ProcessEnv {
  param([string]$Name)
  [System.Environment]::SetEnvironmentVariable($Name, $null, "Process")
}

function Refresh-ConfigFromEnv {
  $script:BackendRoot = Get-EnvValue "BACKEND_ROOT" (Join-Path $script:RootDir "agentsociety")
  $script:RuntimeRoot = Get-EnvValue "RUNTIME_ROOT" (Join-Path $script:RootDir "jiuwenclaw")
  $script:LiveWorkspacePath = Get-EnvValue "LIVE_WORKSPACE_PATH" (Join-Path $script:BackendRoot "quick_experiments")

  $script:RuntimeInstance = Get-EnvValue "RUNTIME_INSTANCE" "god-town"
  $script:RuntimeMode = Get-EnvValue "RUNTIME_MODE" "dev"
  $script:RuntimeLanguage = Get-EnvValue "RUNTIME_LANGUAGE" "zh"
  $script:RuntimeLegacyInstances = (Get-EnvValue "RUNTIME_LEGACY_INSTANCES" "jiuwenclaw-town jiuwenclaw-town-native-skill").Split(" ", [System.StringSplitOptions]::RemoveEmptyEntries)
  $script:RuntimeAgentPort = [int](Get-EnvValue "RUNTIME_AGENT_PORT" "19092")
  $script:RuntimeWebPort = [int](Get-EnvValue "RUNTIME_WEB_PORT" "20000")
  $script:RuntimeGatewayPort = [int](Get-EnvValue "RUNTIME_GATEWAY_PORT" "20001")
  $script:RuntimeUiPort = [int](Get-EnvValue "RUNTIME_UI_PORT" "6173")
  $script:GodExtraStopPorts = (Get-EnvValue "GOD_EXTRA_STOP_PORTS" "20092 21000 21001 7173").Split(" ", [System.StringSplitOptions]::RemoveEmptyEntries) | ForEach-Object { [int]$_ }

  $script:GodExperiment = Get-EnvValue "GOD_EXPERIMENT" (Get-EnvValue "GOD_HYPOTHESIS_ID" "god_town")
  $script:GodExperimentRun = Get-EnvValue "GOD_EXPERIMENT_RUN" (Get-EnvValue "GOD_EXPERIMENT_ID" "1")
  $script:GodBackendHost = Get-EnvValue "GOD_BACKEND_HOST" (Get-EnvValue "BACKEND_HOST" "127.0.0.1")
  $script:GodBackendPort = [int](Get-EnvValue "GOD_BACKEND_PORT" (Get-EnvValue "BACKEND_PORT" "8001"))
  $script:GodFrontendPort = [int](Get-EnvValue "GOD_FRONTEND_PORT" (Get-EnvValue "AGENTSOCIETY_FRONTEND_PORT" "5174"))
  $script:GodLiveStepTimeout = Get-EnvValue "GOD_LIVE_STEP_TIMEOUT" (Get-EnvValue "AGENTSOCIETY_LIVE_STEP_TIMEOUT" "900")

  $script:BackendUrl = "http://$($script:GodBackendHost):$($script:GodBackendPort)"
  $script:FrontendUrl = "http://127.0.0.1:$($script:GodFrontendPort)"
  $script:RuntimeUiUrl = "http://localhost:$($script:RuntimeUiPort)"
}

Refresh-ConfigFromEnv

function Show-Usage {
  @"
Usage: .\scripts\god.ps1 [menu|setup|configure|start|restart|new-run|stop|status|tail|open]

menu      Interactive menu.
setup     Install or check Python and Node dependencies only.
configure Open the experiment setup wizard and wait for a new experiment request.
start     Start GOD (idempotent; reuses running services) and open frontend pages.
restart   Stop everything cleanly, then start.
new-run   Stop, wipe the current run, then start a fresh session.
stop      Stop GOD and release its ports.
status    Print URLs, ports, and model status.
tail      Follow GOD service logs.
open      Open the GOD frontend pages in the default browser.
"@ | Write-Host
}

function Update-ProcessPath {
  $currentPath = $env:Path
  $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
  $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
  $localBin = Join-Path $HOME ".local\bin"
  $parts = @($currentPath, $machinePath, $userPath, $localBin) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
  $env:Path = ($parts -join [System.IO.Path]::PathSeparator)
}

function Require-Winget {
  if (-not (Test-CommandExists "winget")) {
    Stop-God "winget is required to auto-install Git and Node.js on Windows. Install App Installer from Microsoft Store, then rerun this command."
  }
}

function Install-WingetPackage {
  param(
    [string]$Id,
    [string]$Name
  )
  Require-Winget
  Write-GodLog "Installing $Name with winget"
  & winget install --id $Id -e --accept-package-agreements --accept-source-agreements
  if ($LASTEXITCODE -ne 0) {
    Stop-God "winget failed to install $Name ($Id)"
  }
  Update-ProcessPath
}

function Install-Uv {
  Write-GodLog "Installing uv"
  Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
  Update-ProcessPath
  if (-not (Test-CommandExists "uv")) {
    Stop-God "uv was installed but is not available on PATH. Open a new PowerShell window and rerun this command."
  }
}

function Test-NpmAvailable {
  return (Test-CommandExists "npm.cmd") -or (Test-CommandExists "npm")
}

function Ensure-Prerequisites {
  if (-not (Test-CommandExists "uv")) {
    Install-Uv
  }
  if (-not (Test-CommandExists "git")) {
    Install-WingetPackage "Git.Git" "Git"
  }
  if (-not (Test-NpmAvailable)) {
    Install-WingetPackage "OpenJS.NodeJS.LTS" "Node.js LTS"
  }

  Update-ProcessPath
  foreach ($tool in @("uv", "git")) {
    if (-not (Test-CommandExists $tool)) {
      Stop-God "$tool is not available after installation. Open a new PowerShell window and rerun this command."
    }
  }
  if (-not (Test-NpmAvailable)) {
    Stop-God "npm is not available after Node.js installation. Open a new PowerShell window and rerun this command."
  }
}

function Read-DotEnv {
  if (-not (Test-Path $script:EnvFile)) {
    return
  }
  foreach ($line in [System.IO.File]::ReadAllLines($script:EnvFile)) {
    if ($line -match '^\s*#' -or $line -notmatch '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
      continue
    }
    $key = $Matches[1]
    $value = $Matches[2].Trim()
    if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
      if ($value.Length -ge 2) {
        $value = $value.Substring(1, $value.Length - 2)
      }
    }
    Set-ProcessEnv $key $value
  }
}

function Set-EnvValue {
  param(
    [string]$Key,
    [string]$Value
  )
  $lines = @()
  if (Test-Path $script:EnvFile) {
    $lines = [System.IO.File]::ReadAllLines($script:EnvFile)
  }
  $out = New-Object System.Collections.Generic.List[string]
  $seen = $false
  foreach ($line in $lines) {
    if ($line -like "$Key=*") {
      $out.Add("$Key=$Value")
      $seen = $true
    } else {
      $out.Add($line)
    }
  }
  if (-not $seen) {
    if ($out.Count -gt 0 -and $out[$out.Count - 1] -ne "") {
      $out.Add("")
    }
    $out.Add("$Key=$Value")
  }
  Write-TextUtf8NoBom $script:EnvFile (($out -join "`n").TrimEnd() + "`n")
  Set-ProcessEnv $Key $Value
  Refresh-ConfigFromEnv
}

function Set-EnvValuesInFile {
  param(
    [string]$Path,
    [hashtable]$Values
  )
  $lines = @()
  if (Test-Path $Path) {
    $lines = [System.IO.File]::ReadAllLines($Path)
  }
  $out = New-Object System.Collections.Generic.List[string]
  $seen = @{}
  foreach ($line in $lines) {
    $replaced = $false
    foreach ($key in $Values.Keys) {
      if ($line -like "$key=*") {
        $out.Add("$key=$($Values[$key])")
        $seen[$key] = $true
        $replaced = $true
        break
      }
    }
    if (-not $replaced) {
      $out.Add($line)
    }
  }
  foreach ($key in $Values.Keys) {
    if (-not $seen.ContainsKey($key)) {
      if ($out.Count -gt 0 -and $out[$out.Count - 1] -ne "") {
        $out.Add("")
      }
      $out.Add("$key=$($Values[$key])")
    }
  }
  Write-TextUtf8NoBom $Path (($out -join "`n").TrimEnd() + "`n")
}

function Set-ObjectProperty {
  param(
    [object]$Object,
    [string]$Name,
    [object]$Value
  )
  if ($Object.PSObject.Properties[$Name]) {
    $Object.$Name = $Value
  } else {
    $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
  }
}

function Get-ObjectPropertyValue {
  param(
    [AllowNull()][object]$Object,
    [string]$Name,
    [AllowNull()][object]$Default = $null
  )
  if ($null -ne $Object -and $Object.PSObject.Properties[$Name]) {
    return $Object.$Name
  }
  return $Default
}

function Export-InternalEnv {
  $godLlmKey = Get-EnvValue "GOD_LLM_API_KEY" (Get-EnvValue "AGENTSOCIETY_LLM_API_KEY" (Get-EnvValue "JIUWENCLAW_API_KEY" ""))
  $godLlmBase = Get-EnvValue "GOD_LLM_API_BASE" (Get-EnvValue "AGENTSOCIETY_LLM_API_BASE" (Get-EnvValue "JIUWENCLAW_API_BASE" ""))
  $godLlmModel = Get-EnvValue "GOD_LLM_MODEL" (Get-EnvValue "AGENTSOCIETY_LLM_MODEL" (Get-EnvValue "JIUWENCLAW_MODEL" ""))
  $godEmbeddingKey = Get-EnvValue "GOD_EMBEDDING_API_KEY" (Get-EnvValue "AGENTSOCIETY_EMBEDDING_API_KEY" (Get-EnvValue "JIUWENCLAW_EMBED_API_KEY" ""))
  $godEmbeddingBase = Get-EnvValue "GOD_EMBEDDING_API_BASE" (Get-EnvValue "AGENTSOCIETY_EMBEDDING_API_BASE" (Get-EnvValue "JIUWENCLAW_EMBED_API_BASE" ""))
  $godEmbeddingModel = Get-EnvValue "GOD_EMBEDDING_MODEL" (Get-EnvValue "AGENTSOCIETY_EMBEDDING_MODEL" (Get-EnvValue "JIUWENCLAW_EMBED_MODEL" ""))

  if ([string]::IsNullOrEmpty($godLlmBase)) { $godLlmBase = "https://api.openai.com/v1" }
  if ([string]::IsNullOrEmpty($godLlmModel)) { $godLlmModel = "gpt-5.4" }
  $nanoModel = Get-EnvValue "GOD_LLM_NANO_MODEL" ""
  if ([string]::IsNullOrEmpty($nanoModel)) {
    if ($godLlmModel -eq "gpt-5.4") {
      $nanoModel = "gpt-5.4-nano"
    } else {
      $nanoModel = ($godLlmModel -replace '\.[^.]*$', '') + ".*-nano"
    }
  }
  if ([string]::IsNullOrEmpty($godEmbeddingKey)) { $godEmbeddingKey = $godLlmKey }
  if ([string]::IsNullOrEmpty($godEmbeddingBase)) { $godEmbeddingBase = $godLlmBase }
  if ([string]::IsNullOrEmpty($godEmbeddingModel)) { $godEmbeddingModel = "text-embedding-3-large" }

  Set-ProcessEnv "GOD_LLM_API_KEY" $godLlmKey
  Set-ProcessEnv "GOD_LLM_API_BASE" $godLlmBase
  Set-ProcessEnv "GOD_LLM_MODEL" $godLlmModel
  Set-ProcessEnv "GOD_EMBEDDING_API_KEY" $godEmbeddingKey
  Set-ProcessEnv "GOD_EMBEDDING_API_BASE" $godEmbeddingBase
  Set-ProcessEnv "GOD_EMBEDDING_MODEL" $godEmbeddingModel

  Set-ProcessEnv "AGENTSOCIETY_LLM_API_KEY" $godLlmKey
  Set-ProcessEnv "AGENTSOCIETY_LLM_API_BASE" $godLlmBase
  Set-ProcessEnv "AGENTSOCIETY_LLM_MODEL" $godLlmModel
  Set-ProcessEnv "AGENTSOCIETY_NANO_LLM_MODEL" $nanoModel
  Set-ProcessEnv "AGENTSOCIETY_EMBEDDING_API_KEY" $godEmbeddingKey
  Set-ProcessEnv "AGENTSOCIETY_EMBEDDING_API_BASE" $godEmbeddingBase
  Set-ProcessEnv "AGENTSOCIETY_EMBEDDING_MODEL" $godEmbeddingModel

  Set-ProcessEnv "JIUWENCLAW_API_KEY" $godLlmKey
  Set-ProcessEnv "JIUWENCLAW_API_BASE" $godLlmBase
  Set-ProcessEnv "JIUWENCLAW_MODEL" $godLlmModel
  Set-ProcessEnv "JIUWENCLAW_MODEL_PROVIDER" (Get-EnvValue "JIUWENCLAW_MODEL_PROVIDER" "OpenAI")
  Set-ProcessEnv "JIUWENCLAW_EMBED_API_KEY" $godEmbeddingKey
  Set-ProcessEnv "JIUWENCLAW_EMBED_API_BASE" $godEmbeddingBase
  Set-ProcessEnv "JIUWENCLAW_EMBED_MODEL" $godEmbeddingModel

  Set-ProcessEnv "BACKEND_HOST" $script:GodBackendHost
  Set-ProcessEnv "BACKEND_PORT" ([string]$script:GodBackendPort)
  Set-ProcessEnv "AGENTSOCIETY_FRONTEND_PORT" ([string]$script:GodFrontendPort)
  Set-ProcessEnv "GOD_HYPOTHESIS_ID" $script:GodExperiment
  Set-ProcessEnv "GOD_EXPERIMENT_ID" $script:GodExperimentRun
}

function Load-CurrentExperiment {
  if (-not (Test-Path $script:CurrentExperimentFile)) {
    return
  }
  try {
    $data = Get-Content $script:CurrentExperimentFile -Raw | ConvertFrom-Json
  } catch {
    return
  }
  $hypothesisId = Get-ObjectPropertyValue $data "hypothesis_id" ""
  $experimentId = Get-ObjectPropertyValue $data "experiment_id" ""
  $workspacePath = Get-ObjectPropertyValue $data "workspace_path" ""
  if (($script:InitialEnv.GOD_EXPERIMENT -eq $null) -and ($script:InitialEnv.GOD_HYPOTHESIS_ID -eq $null) -and $hypothesisId) {
    Set-ProcessEnv "GOD_EXPERIMENT" ([string]$hypothesisId)
  }
  if (($script:InitialEnv.GOD_EXPERIMENT_RUN -eq $null) -and ($script:InitialEnv.GOD_EXPERIMENT_ID -eq $null) -and $experimentId) {
    Set-ProcessEnv "GOD_EXPERIMENT_RUN" ([string]$experimentId)
  }
  if (($script:InitialEnv.LIVE_WORKSPACE_PATH -eq $null) -and $workspacePath) {
    Set-ProcessEnv "LIVE_WORKSPACE_PATH" ([string]$workspacePath)
  }
}

function Load-Env {
  Read-DotEnv

  if ($script:InitialEnv.GOD_EXPERIMENT -ne $null) {
    Set-ProcessEnv "GOD_EXPERIMENT" $script:InitialEnv.GOD_EXPERIMENT
  } elseif ($script:InitialEnv.GOD_HYPOTHESIS_ID -ne $null) {
    Set-ProcessEnv "GOD_EXPERIMENT" $script:InitialEnv.GOD_HYPOTHESIS_ID
  } else {
    Remove-ProcessEnv "GOD_EXPERIMENT"
    Remove-ProcessEnv "GOD_HYPOTHESIS_ID"
  }

  if ($script:InitialEnv.GOD_EXPERIMENT_RUN -ne $null) {
    Set-ProcessEnv "GOD_EXPERIMENT_RUN" $script:InitialEnv.GOD_EXPERIMENT_RUN
  } elseif ($script:InitialEnv.GOD_EXPERIMENT_ID -ne $null) {
    Set-ProcessEnv "GOD_EXPERIMENT_RUN" $script:InitialEnv.GOD_EXPERIMENT_ID
  } else {
    Remove-ProcessEnv "GOD_EXPERIMENT_RUN"
    Remove-ProcessEnv "GOD_EXPERIMENT_ID"
  }

  if ($script:InitialEnv.LIVE_WORKSPACE_PATH -ne $null) {
    Set-ProcessEnv "LIVE_WORKSPACE_PATH" $script:InitialEnv.LIVE_WORKSPACE_PATH
  }
  if ($script:InitialEnv.GOD_MAP_ID -ne $null) {
    Set-ProcessEnv "GOD_MAP_ID" $script:InitialEnv.GOD_MAP_ID
  } else {
    Remove-ProcessEnv "GOD_MAP_ID"
  }

  Refresh-ConfigFromEnv
  Export-InternalEnv
  Load-CurrentExperiment
  Refresh-ConfigFromEnv
  Export-InternalEnv
  Refresh-ConfigFromEnv
}

function Get-ConfiguredState {
  param([string]$Value)
  if ([string]::IsNullOrEmpty($Value)) {
    return "missing"
  }
  return "configured"
}

function Get-RuntimeWorkspace {
  return Join-PathMany $HOME ".jiuwenclaw-instances" $script:RuntimeInstance
}

function Ensure-EnvFile {
  $envWasCreated = $false
  if (-not (Test-Path $script:EnvFile)) {
    Copy-Item (Join-Path $script:RootDir ".env.example") $script:EnvFile
    $envWasCreated = $true
    Write-GodLog "Created .env from .env.example"
  }

  Load-Env

  if ((Get-EnvValue "GOD_SETUP_MODE" "0") -eq "1") {
    Set-EnvValue "GOD_LLM_API_BASE" (Get-EnvValue "GOD_LLM_API_BASE" "https://api.openai.com/v1")
    Set-EnvValue "GOD_LLM_MODEL" (Get-EnvValue "GOD_LLM_MODEL" "gpt-5.4")
    Set-EnvValue "GOD_EMBEDDING_MODEL" (Get-EnvValue "GOD_EMBEDDING_MODEL" "text-embedding-3-large")
    Load-Env
    return
  }

  if ([string]::IsNullOrEmpty((Get-EnvValue "GOD_LLM_API_KEY" ""))) {
    if ([Environment]::UserInteractive) {
      $secureKey = Read-Host "[GOD] LLM API key is required. Paste it now" -AsSecureString
      $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
      try {
        $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
      } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
      }
      if ([string]::IsNullOrEmpty($apiKey)) {
        Stop-God "LLM API key is empty"
      }
      Set-EnvValue "GOD_LLM_API_KEY" $apiKey
    } else {
      Stop-God "GOD_LLM_API_KEY is empty. Fill $($script:EnvFile) first."
    }
  }

  if ($envWasCreated -and [Environment]::UserInteractive) {
    $defaultApiBase = Get-EnvValue "GOD_LLM_API_BASE" "https://api.openai.com/v1"
    $defaultModel = Get-EnvValue "GOD_LLM_MODEL" "gpt-5.4"
    $apiBaseInput = Read-Host "[GOD] LLM API base URL [$defaultApiBase]"
    $modelInput = Read-Host "[GOD] LLM model [$defaultModel]"
    if ([string]::IsNullOrEmpty($apiBaseInput)) { $apiBaseInput = $defaultApiBase }
    if ([string]::IsNullOrEmpty($modelInput)) { $modelInput = $defaultModel }
    Set-EnvValue "GOD_LLM_API_BASE" $apiBaseInput
    Set-EnvValue "GOD_LLM_MODEL" $modelInput
  }

  Set-EnvValue "GOD_LLM_API_BASE" (Get-EnvValue "GOD_LLM_API_BASE" "https://api.openai.com/v1")
  Set-EnvValue "GOD_LLM_MODEL" (Get-EnvValue "GOD_LLM_MODEL" "gpt-5.4")
  Set-EnvValue "GOD_EMBEDDING_MODEL" (Get-EnvValue "GOD_EMBEDDING_MODEL" "text-embedding-3-large")
  Load-Env
}

function Test-PortOpen {
  param([int]$Port)
  foreach ($connectHost in @("127.0.0.1", "::1", "localhost")) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
      $async = $client.BeginConnect($connectHost, $Port, $null, $null)
      if ($async.AsyncWaitHandle.WaitOne(350)) {
        $client.EndConnect($async)
        return $true
      }
    } catch {
    } finally {
      $client.Close()
    }
  }
  return $false
}

function Wait-ForPort {
  param(
    [int]$Port,
    [string]$Label,
    [int]$TimeoutSeconds = 90
  )
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-PortOpen $Port) {
      Write-GodLog "$Label ready on port $Port"
      return
    }
    Start-Sleep -Seconds 1
  }
  Write-WaitTimeoutContext $Label $Port
  Stop-God "Timed out waiting for $Label on port $Port"
}

function Write-WaitTimeoutContext {
  param(
    [string]$Label,
    [int]$Port
  )
  Write-GodDiagnostic "[GOD] timeout diagnostics for $Label on port $Port"
  try {
    Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
      Format-Table -AutoSize |
      Out-String |
      ForEach-Object { Write-GodDiagnostic $_ }
  } catch {
  }
  if ($Label -like "Agent runtime*" -and (Test-Path $script:RuntimeLog)) {
    Write-GodDiagnostic "[GOD] recent runtime log:"
    Get-Content $script:RuntimeLog -Tail 80 | ForEach-Object { Write-GodDiagnostic $_ }
  }
  if ($Label -eq "Backend" -and (Test-Path $script:BackendLog)) {
    Write-GodDiagnostic "[GOD] recent backend log:"
    Get-Content $script:BackendLog -Tail 80 | ForEach-Object { Write-GodDiagnostic $_ }
  }
}

function ConvertTo-UrlEncoded {
  param([string]$Value)
  return [System.Uri]::EscapeDataString($Value)
}

function Get-ReplayUrl {
  return "$($script:FrontendUrl)/pixel-replay/$($script:GodExperiment)/$($script:GodExperimentRun)"
}

function Get-SessionUrl {
  $workspace = ConvertTo-UrlEncoded $script:LiveWorkspacePath
  return "$($script:BackendUrl)/api/v1/live-experiments/$($script:GodExperiment)/$($script:GodExperimentRun)/sessions?workspace_path=$workspace"
}

function Get-RunStepUrl {
  $workspace = ConvertTo-UrlEncoded $script:LiveWorkspacePath
  return "$($script:BackendUrl)/api/v1/live-experiments/$($script:GodExperiment)/$($script:GodExperimentRun)/run-step?workspace_path=$workspace"
}

function Get-StopLiveUrl {
  $workspace = ConvertTo-UrlEncoded $script:LiveWorkspacePath
  return "$($script:BackendUrl)/api/v1/live-experiments/$($script:GodExperiment)/$($script:GodExperimentRun)/stop?workspace_path=$workspace"
}

function Get-SetupUrl {
  return "$($script:FrontendUrl)/setup"
}

function Show-FrontendLinks {
  Write-Host ("Control room:     {0}" -f (Get-ReplayUrl))
  Write-Host ("Agent runtime UI: {0}" -f $script:RuntimeUiUrl)
}

function Open-BrowserWindow {
  param([string]$Url)
  if ((Get-EnvValue "GOD_OPEN_BROWSER" "1") -ne "1") {
    return
  }
  Start-Process $Url | Out-Null
}

function Open-FrontendPages {
  Write-GodLog "Opening frontend pages"
  Open-BrowserWindow (Get-ReplayUrl)
  Open-BrowserWindow $script:RuntimeUiUrl
}

function Open-SetupPage {
  Write-GodLog "Opening setup wizard"
  Open-BrowserWindow (Get-SetupUrl)
  Write-Host ("Setup wizard:     {0}" -f (Get-SetupUrl))
}

function Get-CurrentExperimentConfigPath {
  if (-not (Test-Path $script:CurrentExperimentFile)) {
    return $null
  }
  try {
    $data = Get-Content $script:CurrentExperimentFile -Raw | ConvertFrom-Json
  } catch {
    return $null
  }
  $hypothesisId = [string](Get-ObjectPropertyValue $data "hypothesis_id" "")
  $rawExperimentId = Get-ObjectPropertyValue $data "experiment_id" ""
  $experimentId = if ($rawExperimentId) { [string]$rawExperimentId } else { "1" }
  if ([string]::IsNullOrWhiteSpace($hypothesisId) -or [string]::IsNullOrWhiteSpace($experimentId)) {
    return $null
  }
  $rawWorkspace = Get-ObjectPropertyValue $data "workspace_path" ""
  $workspace = if ($rawWorkspace) { [string]$rawWorkspace } else { $script:LiveWorkspacePath }
  return Join-PathMany $workspace "hypothesis_$hypothesisId" "experiment_$experimentId" "init" "init_config.json"
}

function Test-CurrentExperimentConfig {
  $configPath = Get-CurrentExperimentConfigPath
  return (-not [string]::IsNullOrEmpty($configPath)) -and (Test-Path $configPath)
}

function Test-PendingStartRequest {
  if (-not (Test-Path $script:StartRequestFile)) {
    return $false
  }
  if ((Test-Path $script:CurrentExperimentFile) -and ((Get-Item $script:StartRequestFile).LastWriteTime -lt (Get-Item $script:CurrentExperimentFile).LastWriteTime)) {
    $stalePath = "$($script:StartRequestFile).stale.$((Get-Date).ToString('yyyyMMdd_HHmmss'))"
    Write-GodLog "Ignoring stale setup startup request: $($script:StartRequestFile)"
    try {
      Move-Item $script:StartRequestFile $stalePath -Force
    } catch {
      Remove-Item $script:StartRequestFile -Force -ErrorAction SilentlyContinue
    }
    return $false
  }
  return $true
}

function Test-ReadyStartConfig {
  Load-Env
  return (-not [string]::IsNullOrEmpty((Get-EnvValue "GOD_LLM_API_KEY" ""))) -and (Test-CurrentExperimentConfig)
}

function Require-CurrentExperimentConfig {
  if (-not (Test-CurrentExperimentConfig)) {
    Stop-God "No current experiment is configured. Run .\scripts\god.ps1 start and choose an experiment in setup."
  }
}

function Stop-ProcessTree {
  param([int]$ProcessId)
  if ($ProcessId -le 0) {
    return
  }
  try {
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId" -ErrorAction SilentlyContinue
    foreach ($child in $children) {
      Stop-ProcessTree -ProcessId ([int]$child.ProcessId)
    }
  } catch {
  }
  try {
    $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($proc) {
      Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    }
  } catch {
  }
}

function Stop-PidFile {
  param(
    [string]$Path,
    [string]$Label
  )
  if (-not (Test-Path $Path)) {
    return
  }
  $processIdText = (Get-Content $Path -ErrorAction SilentlyContinue | Select-Object -First 1)
  $processId = 0
  [int]::TryParse($processIdText, [ref]$processId) | Out-Null
  if ($processId -gt 0 -and (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
    Write-GodLog "Stopping $Label pid=$processId"
    Stop-ProcessTree -ProcessId $processId
  }
  Remove-Item $Path -Force -ErrorAction SilentlyContinue
}

function Stop-ListenersOnPort {
  param([int]$Port)
  $processIds = @()
  try {
    $processIds = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
      Select-Object -ExpandProperty OwningProcess -Unique)
  } catch {
    $processIds = @()
  }

  if ($processIds.Count -eq 0) {
    try {
      $processIds = @(netstat -ano -p tcp |
        Select-String "LISTENING" |
        Where-Object { $_.Line -match "[:.]$Port\s" } |
        ForEach-Object { ($_ -split '\s+')[-1] } |
        Select-Object -Unique)
    } catch {
      $processIds = @()
    }
  }

  $processIds = @($processIds | Where-Object { $_ -and ([int]$_) -gt 0 } | Select-Object -Unique)
  if ($processIds.Count -eq 0) {
    return
  }
  Write-GodLog "Clearing port $Port"
  foreach ($processId in $processIds) {
    Stop-ProcessTree -ProcessId ([int]$processId)
  }
}

function Stop-ControlServices {
  Stop-PidFile $script:FrontendPidFile "control room"
  Stop-PidFile $script:BackendPidFile "backend"
  Stop-ListenersOnPort $script:GodFrontendPort
  Stop-ListenersOnPort $script:GodBackendPort
}

function Stop-LivePorts {
  $ports = @(
    $script:GodBackendPort,
    $script:GodFrontendPort,
    $script:RuntimeAgentPort,
    $script:RuntimeWebPort,
    $script:RuntimeGatewayPort,
    $script:RuntimeUiPort
  ) + $script:GodExtraStopPorts
  foreach ($port in $ports) {
    Stop-ListenersOnPort ([int]$port)
  }
}

function Start-DetachedService {
  param(
    [string]$SessionName,
    [string]$PidFile,
    [string]$Command,
    [string]$LogPath = ""
  )
  $psExe = (Get-Process -Id $PID).Path
  if ([string]::IsNullOrEmpty($psExe)) {
    $psExe = "powershell.exe"
  }
  if (-not [string]::IsNullOrEmpty($LogPath)) {
    $Command = @(
      "`$ErrorActionPreference = 'Stop'",
      "try {",
      $Command,
      "} catch {",
      "  '[GOD] service startup error' | Out-File -FilePath $(Quote-PSLiteral $LogPath) -Append -Encoding utf8",
      "  `$_.Exception.Message | Out-File -FilePath $(Quote-PSLiteral $LogPath) -Append -Encoding utf8",
      "  `$_.ScriptStackTrace | Out-File -FilePath $(Quote-PSLiteral $LogPath) -Append -Encoding utf8",
      "  exit 1",
      "}"
    ) -join "`n"
  }
  $encoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($Command))
  $process = Start-Process -FilePath $psExe `
    -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", $encoded) `
    -PassThru `
    -WindowStyle Hidden
  Write-TextUtf8NoBom $PidFile ("$($process.Id)`n")
  Start-Sleep -Seconds 2
  if (-not (Get-Process -Id $process.Id -ErrorAction SilentlyContinue)) {
    if (-not [string]::IsNullOrEmpty($LogPath) -and (Test-Path $LogPath)) {
      Write-GodDiagnostic "[GOD] recent $SessionName log ($LogPath):"
      Get-Content $LogPath -Tail 80 -ErrorAction SilentlyContinue | ForEach-Object { Write-GodDiagnostic $_ }
    }
    Stop-God "$SessionName exited during startup. See $LogPath"
  }
}

function Stop-RuntimeInstance {
  param([string]$Name)
  if (-not (Test-Path $script:RuntimeRoot)) {
    return
  }
  if (-not (Test-CommandExists "uv")) {
    return
  }
  Push-Location $script:RuntimeRoot
  try {
    Invoke-NativeCommand -FilePath (Get-ToolPath @("uv")) -ArgumentList @("run", "jiuwenclaw-start", "--stop", $Name) *> $null
  } catch {
  } finally {
    Pop-Location
  }
}

function Stop-All {
  Write-GodLog "Stopping GOD services"
  if (Test-PortOpen $script:GodBackendPort) {
    try {
      Invoke-RestMethod -Method Post -Uri (Get-StopLiveUrl) | Out-Null
    } catch {
    }
  }
  Stop-PidFile $script:FrontendPidFile "control room"
  Stop-PidFile $script:BackendPidFile "backend"
  Stop-PidFile $script:RuntimePidFile "agent runtime"
  Stop-RuntimeInstance $script:RuntimeInstance
  foreach ($name in $script:RuntimeLegacyInstances) {
    Stop-RuntimeInstance $name
  }
  Stop-LivePorts
}

function Remove-PathSafe {
  param(
    [string]$Path,
    [string]$Label
  )
  if (Test-Path $Path) {
    Write-GodLog "Removing $Label"
    Remove-Item $Path -Recurse -Force -ErrorAction SilentlyContinue
  }
}

function Remove-ExperimentRuns {
  if (-not (Test-Path $script:LiveWorkspacePath)) {
    return
  }
  Write-GodLog "Removing experiment run directories"
  Get-ChildItem -Path $script:LiveWorkspacePath -Directory -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq "run" -or $_.Name -like "run_*" } |
    ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
}

function Remove-RuntimeRegistryEntries {
  if (-not (Test-Path $script:RuntimeRoot) -or -not (Test-CommandExists "uv")) {
    return
  }
  $names = @($script:RuntimeInstance) + $script:RuntimeLegacyInstances
  $nameArgs = ($names | ForEach-Object { Quote-PSLiteral $_ }) -join ", "
  $code = @"
from pathlib import Path
from ruamel.yaml import YAML

names = {$nameArgs}
path = Path.home() / ".jiuwenclaw" / "instances.yaml"
if not path.exists():
    raise SystemExit(0)
yaml = YAML()
data = yaml.load(path.read_text(encoding="utf-8")) or {}
instances = data.get("instances")
if not isinstance(instances, dict):
    raise SystemExit(0)
for name in names:
    instances.pop(name, None)
if instances:
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f)
else:
    path.unlink()
"@
  Push-Location $script:RuntimeRoot
  try {
    $code | & (Get-ToolPath @("uv")) run python -
  } catch {
    Write-GodLog "Could not update runtime registry; continuing reset"
  } finally {
    Pop-Location
  }
}

function Reset-Factory {
  Ensure-Prerequisites
  Write-GodLog "Factory reset"
  Stop-All
  Remove-ExperimentRuns
  Remove-RuntimeRegistryEntries
  foreach ($name in @($script:RuntimeInstance) + $script:RuntimeLegacyInstances) {
    Remove-PathSafe (Join-PathMany $HOME ".jiuwenclaw-instances" $name) "runtime instance state"
  }
  Remove-PathSafe $script:EnvFile ".env"
  Remove-PathSafe $script:StateDir "state and logs"
  Remove-PathSafe (Join-Path $script:BackendRoot ".venv") "backend virtualenv"
  Remove-PathSafe (Join-Path $script:RuntimeRoot ".venv") "runtime virtualenv"
  Remove-PathSafe (Join-PathMany $script:BackendRoot "frontend" "node_modules") "frontend dependencies"
  Remove-PathSafe (Join-PathMany $script:RuntimeRoot "jiuwenclaw" "channels" "web" "frontend" "node_modules") "runtime UI dependencies"
  Write-GodLog "Factory reset complete."
}

function Invoke-NativeCommand {
  param(
    [Parameter(ValueFromPipeline = $true)]
    [AllowNull()][object]$InputObject,
    [string]$FilePath,
    [object[]]$ArgumentList,
    [string]$LogPath = ""
  )
  begin {
    $previousEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $pipelineInput = New-Object System.Collections.Generic.List[object]
  }
  process {
    if ($null -ne $InputObject) {
      $pipelineInput.Add($InputObject)
    }
  }
  end {
    try {
      $hasInput = $pipelineInput.Count -gt 0
      $inputText = if ($hasInput) { ($pipelineInput | ForEach-Object { [string]$_ }) -join [Environment]::NewLine } else { $null }
      if ($LogPath) {
        if ($hasInput) {
          $inputText | & $FilePath @ArgumentList 2>&1 | Out-File -FilePath $LogPath -Append -Encoding utf8
        } else {
          & $FilePath @ArgumentList 2>&1 | Out-File -FilePath $LogPath -Append -Encoding utf8
        }
      } else {
        if ($hasInput) {
          $inputText | & $FilePath @ArgumentList
        } else {
          & $FilePath @ArgumentList
        }
      }
    } finally {
      $ErrorActionPreference = $previousEap
    }
  }
}

function Get-DetachedNativeExecLine {
  param(
    [string]$FilePath,
    [string]$ArgumentExpression,
    [string]$LogPath = ""
  )
  $redirect = if ($LogPath) {
    " 2>&1 | Out-File -FilePath $(Quote-PSLiteral $LogPath) -Append -Encoding utf8"
  } else {
    ""
  }
  return "`$ErrorActionPreference = 'Continue'; & $(Quote-PSLiteral $FilePath) $ArgumentExpression$redirect; if (`$LASTEXITCODE -ne 0) { exit `$LASTEXITCODE }"
}

function Invoke-CheckedCommand {
  param(
    [string]$FilePath,
    [string[]]$Arguments,
    [string]$WorkingDirectory
  )
  Push-Location $WorkingDirectory
  try {
    Invoke-NativeCommand -FilePath $FilePath -ArgumentList $Arguments
    if ($LASTEXITCODE -ne 0) {
      Stop-God "Command failed: $FilePath $($Arguments -join ' ')"
    }
  } finally {
    Pop-Location
  }
}

function Ensure-BackendDependencies {
  if ((Get-EnvValue "GOD_SKIP_SETUP" "0") -eq "1") {
    return
  }
  $uv = Get-ToolPath @("uv")
  Write-GodLog "Ensuring backend Python dependencies (first run may take several minutes)"
  Invoke-CheckedCommand -FilePath $uv -Arguments @("sync", "--managed-python") -WorkingDirectory $script:BackendRoot
}

function Setup-Dependencies {
  Ensure-Prerequisites
  if ((Get-EnvValue "GOD_SKIP_SETUP" "0") -eq "1") {
    Write-GodLog "Skipping dependency setup (GOD_SKIP_SETUP=1)"
    return
  }

  $uv = Get-ToolPath @("uv")
  $npm = Get-ToolPath @("npm.cmd", "npm")

  Write-GodLog "Syncing backend Python dependencies"
  Invoke-CheckedCommand -FilePath $uv -Arguments @("sync", "--managed-python") -WorkingDirectory $script:BackendRoot

  Write-GodLog "Syncing agent runtime Python dependencies"
  Invoke-CheckedCommand -FilePath $uv -Arguments @("sync", "--managed-python") -WorkingDirectory $script:RuntimeRoot

  $backendFrontend = Join-Path $script:BackendRoot "frontend"
  if ((-not (Test-Path (Join-Path $backendFrontend "node_modules"))) -or (Get-EnvValue "GOD_FORCE_SETUP" "0") -eq "1") {
    Write-GodLog "Installing control-room dependencies"
    Invoke-CheckedCommand -FilePath $npm -Arguments @("install", "--no-audit", "--no-fund", "--loglevel=error") -WorkingDirectory $backendFrontend
  }

  $runtimeFrontend = Join-PathMany $script:RuntimeRoot "jiuwenclaw" "channels" "web" "frontend"
  if ((-not (Test-Path (Join-Path $runtimeFrontend "node_modules"))) -or (Get-EnvValue "GOD_FORCE_SETUP" "0") -eq "1") {
    Write-GodLog "Installing runtime UI dependencies"
    Invoke-CheckedCommand -FilePath $npm -Arguments @("install", "--no-audit", "--no-fund", "--loglevel=error") -WorkingDirectory $runtimeFrontend
  }
}

function Sync-RuntimeModelEnv {
  $workspace = Get-RuntimeWorkspace
  if (-not (Test-Path $workspace)) {
    return
  }
  $apiKey = Get-EnvValue "GOD_LLM_API_KEY" ""
  $apiBase = Get-EnvValue "GOD_LLM_API_BASE" ""
  $model = Get-EnvValue "GOD_LLM_MODEL" ""
  if ([string]::IsNullOrEmpty($apiKey) -or [string]::IsNullOrEmpty($apiBase) -or [string]::IsNullOrEmpty($model)) {
    return
  }
  Write-GodLog "Syncing runtime model config"
  $configEnv = Join-PathMany $workspace "config" ".env"
  Set-EnvValuesInFile $configEnv @{
    API_KEY = $apiKey
    API_BASE = $apiBase
    MODEL_NAME = $model
    MODEL_PROVIDER = Get-EnvValue "JIUWENCLAW_MODEL_PROVIDER" "OpenAI"
    EMBED_API_KEY = Get-EnvValue "GOD_EMBEDDING_API_KEY" $apiKey
    EMBED_API_BASE = Get-EnvValue "GOD_EMBEDDING_API_BASE" $apiBase
    EMBED_MODEL = Get-EnvValue "GOD_EMBEDDING_MODEL" ""
  }
}

function Ensure-RuntimeInstance {
  Setup-Dependencies
  $uv = Get-ToolPath @("uv")
  $existing = $false
  Push-Location $script:RuntimeRoot
  try {
    Invoke-NativeCommand -FilePath $uv -ArgumentList @("run", "jiuwenclaw-start", "--status", $script:RuntimeInstance) *> $null
    $existing = ($LASTEXITCODE -eq 0)
  } finally {
    Pop-Location
  }

  if (-not $existing) {
    Write-GodLog "Initializing agent runtime instance (default language: $($script:RuntimeLanguage))"
    Write-TextUtf8NoBom $script:RuntimeInitLog ""
    $workspace = Get-RuntimeWorkspace
    $initInput = if (Test-Path $workspace) { "yes`n$($script:RuntimeLanguage)`n" } else { "$($script:RuntimeLanguage)`n" }
    Push-Location $script:RuntimeRoot
    try {
      $initInput | Invoke-NativeCommand -FilePath $uv -ArgumentList @("run", "jiuwenclaw-init", "--name", $script:RuntimeInstance) -LogPath $script:RuntimeInitLog
      if ($LASTEXITCODE -ne 0) {
        Get-Content $script:RuntimeInitLog -Tail 80 -ErrorAction SilentlyContinue | ForEach-Object { Write-GodDiagnostic $_ }
        Stop-God "Failed to initialize agent runtime instance"
      }
    } finally {
      Pop-Location
    }
  }

  $code = @'
import os
from pathlib import Path
from ruamel.yaml import YAML

name = os.environ["RUNTIME_INSTANCE"]
path = Path.home() / ".jiuwenclaw" / "instances.yaml"
path.parent.mkdir(parents=True, exist_ok=True)
yaml = YAML()
data = yaml.load(path.read_text(encoding="utf-8")) if path.exists() else None
if not isinstance(data, dict):
    data = {"instances": {}}
instances = data.setdefault("instances", {})
entry = instances.setdefault(name, {})
workspace = entry.get("workspace") or str(Path.home() / ".jiuwenclaw-instances" / name)
entry["workspace"] = workspace
entry["ports"] = {
    "agent_server": int(os.environ["RUNTIME_AGENT_PORT"]),
    "web": int(os.environ["RUNTIME_WEB_PORT"]),
    "gateway": int(os.environ["RUNTIME_GATEWAY_PORT"]),
    "frontend": int(os.environ["RUNTIME_UI_PORT"]),
}
with path.open("w", encoding="utf-8") as f:
    yaml.dump(data, f)

workspace_path = Path(workspace).expanduser()
workspace_path.mkdir(parents=True, exist_ok=True)
bootstrap_env = workspace_path / ".env"
bootstrap_env.write_text(
    "\n".join(
        [
            f"# Bootstrap .env for runtime instance: {name}",
            f"JIUWENCLAW_DATA_DIR={workspace_path}",
            f"JIUWENCLAW_INSTANCE={name}",
            f"AGENT_SERVER_PORT={os.environ['RUNTIME_AGENT_PORT']}",
            f"WEB_PORT={os.environ['RUNTIME_WEB_PORT']}",
            f"GATEWAY_PORT={os.environ['RUNTIME_GATEWAY_PORT']}",
            f"FRONTEND_PORT={os.environ['RUNTIME_UI_PORT']}",
            "",
        ]
    ),
    encoding="utf-8",
)
'@
  Set-ProcessEnv "RUNTIME_INSTANCE" $script:RuntimeInstance
  Set-ProcessEnv "RUNTIME_AGENT_PORT" ([string]$script:RuntimeAgentPort)
  Set-ProcessEnv "RUNTIME_WEB_PORT" ([string]$script:RuntimeWebPort)
  Set-ProcessEnv "RUNTIME_GATEWAY_PORT" ([string]$script:RuntimeGatewayPort)
  Set-ProcessEnv "RUNTIME_UI_PORT" ([string]$script:RuntimeUiPort)
  Push-Location $script:RuntimeRoot
  try {
    $code | Invoke-NativeCommand -FilePath $uv -ArgumentList @("run", "python", "-")
    if ($LASTEXITCODE -ne 0) {
      Stop-God "Failed to update runtime instance registry"
    }
  } finally {
    Pop-Location
  }
  Sync-RuntimeModelEnv
}

function Prepare-Experiment {
  $experimentPath = Join-PathMany $script:LiveWorkspacePath "hypothesis_$($script:GodExperiment)" "experiment_$($script:GodExperimentRun)"
  $configPath = Join-PathMany $experimentPath "init" "init_config.json"
  if (-not (Test-Path $configPath)) {
    Stop-God "Experiment config not found: $configPath"
  }

  $sessionPrefix = Get-EnvValue "GOD_SESSION_PREFIX" "$($script:GodExperiment)_run_$($script:GodExperimentRun)"
  Write-GodLog "Preparing experiment: $($script:GodExperiment) (run $($script:GodExperimentRun))"
  $config = Get-Content $configPath -Raw | ConvertFrom-Json
  $agentRoot = (Resolve-Path $script:BackendRoot).Path
  $wsUrl = "ws://127.0.0.1:$($script:RuntimeAgentPort)"
  $requestedMapId = if ($script:InitialEnv.GOD_MAP_ID -ne $null) { Get-EnvValue "GOD_MAP_ID" "" } else { "" }

  foreach ($module in @(Get-ObjectPropertyValue -Object $config -Name "env_modules" -Default @())) {
    if ($null -eq $module) {
      continue
    }
    if ((Get-ObjectPropertyValue $module "module_type" "") -ne "PixelTownSocialEnv") {
      continue
    }
    if (-not $module.PSObject.Properties["kwargs"] -or $null -eq $module.kwargs) {
      Set-ObjectProperty $module "kwargs" ([pscustomobject]@{})
    }
    $kwargs = $module.kwargs
    if (-not [string]::IsNullOrWhiteSpace($requestedMapId)) {
      Set-ObjectProperty $kwargs "map_id" $requestedMapId
      Set-ObjectProperty $kwargs "map_manifest_path" "custom/maps/$requestedMapId/map.yaml"
    } else {
      $mapId = if ($kwargs.PSObject.Properties["map_id"]) { [string]$kwargs.map_id } else { "" }
      $manifestPath = if ($kwargs.PSObject.Properties["map_manifest_path"]) { [string]$kwargs.map_manifest_path } else { "" }
      if ([string]::IsNullOrWhiteSpace($manifestPath)) {
        if ([string]::IsNullOrWhiteSpace($mapId)) {
          $mapId = "the_ville"
          Set-ObjectProperty $kwargs "map_id" $mapId
        }
        Set-ObjectProperty $kwargs "map_manifest_path" "custom/maps/$mapId/map.yaml"
      }
    }
  }

  foreach ($agent in @(Get-ObjectPropertyValue -Object $config -Name "agents" -Default @())) {
    if ($null -eq $agent) {
      continue
    }
    if (-not $agent.PSObject.Properties["kwargs"] -or $null -eq $agent.kwargs) {
      Set-ObjectProperty $agent "kwargs" ([pscustomobject]@{})
    }
    $kwargs = $agent.kwargs
    $agentId = 0
    $rawAgentId = Get-ObjectPropertyValue $agent "agent_id" $null
    $rawKwargsId = Get-ObjectPropertyValue $kwargs "id" $null
    if ($rawAgentId) {
      $agentId = [int]$rawAgentId
    } elseif ($rawKwargsId) {
      $agentId = [int]$rawKwargsId
    }
    Set-ObjectProperty $kwargs "jiuwenclaw_ws_url" $wsUrl
    Set-ObjectProperty $kwargs "session_id" "$sessionPrefix`_agent_$agentId"
    Set-ObjectProperty $kwargs "trusted_dirs" @($agentRoot)
  }

  Write-TextUtf8NoBom $configPath (($config | ConvertTo-Json -Depth 100) + "`n")
}

function Start-Runtime {
  Ensure-RuntimeInstance
  if ((Test-PortOpen $script:RuntimeAgentPort) -and (Test-PortOpen $script:RuntimeWebPort) -and (Test-PortOpen $script:RuntimeGatewayPort) -and (Test-PortOpen $script:RuntimeUiPort)) {
    Write-GodLog "Agent runtime already up"
    return
  }

  Write-GodLog "Starting agent runtime"
  Write-TextUtf8NoBom $script:RuntimeLog ""
  $uv = Get-ToolPath @("uv")
  $runtimeDataDir = Get-RuntimeWorkspace
  $runtimeCmd = @(
    "`$ErrorActionPreference = 'Stop'",
    "Set-Location $(Quote-PSLiteral $script:RuntimeRoot)",
    "`$env:JIUWENCLAW_DATA_DIR = $(Quote-PSLiteral $runtimeDataDir)",
    "`$env:JIUWENCLAW_ROOT = $(Quote-PSLiteral $script:RuntimeRoot)",
    "`$env:JIUWENCLAW_PROJECT_ROOT = $(Quote-PSLiteral $script:RuntimeRoot)",
    "`$env:AGENT_SERVER_PORT = $(Quote-PSLiteral ([string]$script:RuntimeAgentPort))",
    "`$env:WEB_PORT = $(Quote-PSLiteral ([string]$script:RuntimeWebPort))",
    "`$env:GATEWAY_PORT = $(Quote-PSLiteral ([string]$script:RuntimeGatewayPort))",
    "`$env:FRONTEND_PORT = $(Quote-PSLiteral ([string]$script:RuntimeUiPort))",
    (Get-DetachedNativeExecLine -FilePath $uv -ArgumentExpression "run jiuwenclaw-start $(Quote-PSLiteral $script:RuntimeMode) --name $(Quote-PSLiteral $script:RuntimeInstance)" -LogPath $script:RuntimeLog)
  ) -join "; "
  Start-DetachedService -SessionName $script:RuntimeInstance -PidFile $script:RuntimePidFile -Command $runtimeCmd -LogPath $script:RuntimeLog

  Wait-ForPort $script:RuntimeAgentPort "Agent runtime" 180
  Wait-ForPort $script:RuntimeWebPort "Agent runtime web" 120
  Wait-ForPort $script:RuntimeGatewayPort "Agent runtime gateway" 120
  Wait-ForPort $script:RuntimeUiPort "Agent runtime UI" 120
}

function Test-BackendHealthy {
  if (-not (Test-PortOpen $script:GodBackendPort)) {
    return $false
  }
  try {
    Invoke-RestMethod -Uri "$($script:BackendUrl)/health" -TimeoutSec 5 | Out-Null
    return $true
  } catch {
    return $false
  }
}

function Start-Backend {
  Ensure-EnvFile
  if (Test-BackendHealthy) {
    Write-GodLog "Backend already up"
    return
  }

  Ensure-BackendDependencies
  Write-GodLog "Starting backend"
  Write-TextUtf8NoBom $script:BackendLog ""
  $uv = Get-ToolPath @("uv")
  $backendLogLevel = Get-EnvValue "BACKEND_LOG_LEVEL" "info"
  $backendCmd = @(
    "`$ErrorActionPreference = 'Stop'",
    "Set-Location $(Quote-PSLiteral $script:BackendRoot)",
    "`$env:GOD_ROOT = $(Quote-PSLiteral $script:RootDir)",
    "`$env:GOD_ENV_FILE = $(Quote-PSLiteral $script:EnvFile)",
    "`$env:LIVE_WORKSPACE_PATH = $(Quote-PSLiteral $script:LiveWorkspacePath)",
    "`$env:AGENTSOCIETY_LLM_API_KEY = $(Quote-PSLiteral (Get-EnvValue 'AGENTSOCIETY_LLM_API_KEY' ''))",
    "`$env:AGENTSOCIETY_LLM_API_BASE = $(Quote-PSLiteral (Get-EnvValue 'AGENTSOCIETY_LLM_API_BASE' 'https://api.openai.com/v1'))",
    "`$env:AGENTSOCIETY_LLM_MODEL = $(Quote-PSLiteral (Get-EnvValue 'AGENTSOCIETY_LLM_MODEL' 'gpt-5.4'))",
    "`$env:AGENTSOCIETY_NANO_LLM_MODEL = $(Quote-PSLiteral (Get-EnvValue 'AGENTSOCIETY_NANO_LLM_MODEL' 'gpt-5.4-nano'))",
    "`$env:AGENTSOCIETY_EMBEDDING_API_KEY = $(Quote-PSLiteral (Get-EnvValue 'AGENTSOCIETY_EMBEDDING_API_KEY' (Get-EnvValue 'AGENTSOCIETY_LLM_API_KEY' '')))",
    "`$env:AGENTSOCIETY_EMBEDDING_API_BASE = $(Quote-PSLiteral (Get-EnvValue 'AGENTSOCIETY_EMBEDDING_API_BASE' (Get-EnvValue 'AGENTSOCIETY_LLM_API_BASE' 'https://api.openai.com/v1')))",
    "`$env:AGENTSOCIETY_EMBEDDING_MODEL = $(Quote-PSLiteral (Get-EnvValue 'AGENTSOCIETY_EMBEDDING_MODEL' 'text-embedding-3-large'))",
    "`$env:BACKEND_HOST = $(Quote-PSLiteral $script:GodBackendHost)",
    "`$env:BACKEND_PORT = $(Quote-PSLiteral ([string]$script:GodBackendPort))",
    "`$env:AGENTSOCIETY_LIVE_STEP_TIMEOUT = $(Quote-PSLiteral $script:GodLiveStepTimeout)",
    "`$env:BACKEND_LOG_LEVEL = $(Quote-PSLiteral $backendLogLevel)",
    (Get-DetachedNativeExecLine -FilePath $uv -ArgumentExpression "run python -m agentsociety2.backend.run --log-level $(Quote-PSLiteral $backendLogLevel)" -LogPath $script:BackendLog)
  ) -join "; "
  Start-DetachedService -SessionName "god-backend" -PidFile $script:BackendPidFile -Command $backendCmd -LogPath $script:BackendLog

  $backendStartTimeout = [int](Get-EnvValue "GOD_BACKEND_START_TIMEOUT" "180")
  Wait-ForPort $script:GodBackendPort "Backend" $backendStartTimeout
  $deadline = (Get-Date).AddSeconds(30)
  while ((Get-Date) -lt $deadline) {
    if (Test-BackendHealthy) {
      return
    }
    Start-Sleep -Seconds 1
  }
  Stop-God "Backend port is open but /health did not respond"
}

function Start-Frontend {
  if (Test-PortOpen $script:GodFrontendPort) {
    Write-GodLog "Control room already up"
    return
  }

  Write-GodLog "Starting control room"
  Write-TextUtf8NoBom $script:FrontendLog ""
  $npm = Get-ToolPath @("npm.cmd", "npm")
  $frontendRoot = Join-Path $script:BackendRoot "frontend"
  $frontendCmd = @(
    "`$ErrorActionPreference = 'Stop'",
    "Set-Location $(Quote-PSLiteral $frontendRoot)",
    "`$env:VITE_REPLAY_WORKSPACE_PATH = $(Quote-PSLiteral $script:LiveWorkspacePath)",
    "`$env:VITE_DEFAULT_REPLAY_HYPOTHESIS_ID = $(Quote-PSLiteral $script:GodExperiment)",
    "`$env:VITE_DEFAULT_REPLAY_EXPERIMENT_ID = $(Quote-PSLiteral $script:GodExperimentRun)",
    (Get-DetachedNativeExecLine -FilePath $npm -ArgumentExpression "run dev -- --host 127.0.0.1 --port $(Quote-PSLiteral ([string]$script:GodFrontendPort))" -LogPath $script:FrontendLog)
  ) -join "; "
  Start-DetachedService -SessionName "god-frontend" -PidFile $script:FrontendPidFile -Command $frontendCmd -LogPath $script:FrontendLog
  Wait-ForPort $script:GodFrontendPort "Control room" 120
}

function Start-SetupServices {
  Setup-Dependencies
  Set-ProcessEnv "GOD_SETUP_MODE" "1"
  Ensure-EnvFile
  Remove-Item $script:StartRequestFile -Force -ErrorAction SilentlyContinue
  Stop-All
  Start-Backend
  Start-Frontend
  Open-SetupPage
}

function Receive-StartRequest {
  try {
    $data = Get-Content $script:StartRequestFile -Raw | ConvertFrom-Json
  } catch {
    Stop-God "Could not read setup start request"
  }
  $hypothesisId = [string](Get-ObjectPropertyValue $data "hypothesis_id" "")
  $rawExperimentId = Get-ObjectPropertyValue $data "experiment_id" ""
  $experimentId = if ($rawExperimentId) { [string]$rawExperimentId } else { "1" }
  $rawWorkspacePath = Get-ObjectPropertyValue $data "workspace_path" ""
  $workspacePath = if ($rawWorkspacePath) { [string]$rawWorkspacePath } else { "" }
  if ([string]::IsNullOrWhiteSpace($hypothesisId)) {
    Stop-God "Setup start request is missing hypothesis_id"
  }
  try {
    Move-Item $script:StartRequestFile "$($script:StartRequestFile).consumed" -Force
  } catch {
    Remove-Item $script:StartRequestFile -Force -ErrorAction SilentlyContinue
  }
  Set-ProcessEnv "GOD_EXPERIMENT" $hypothesisId
  Set-ProcessEnv "GOD_EXPERIMENT_RUN" $experimentId
  if (-not [string]::IsNullOrWhiteSpace($workspacePath)) {
    Set-ProcessEnv "LIVE_WORKSPACE_PATH" $workspacePath
  }
  Load-Env
  Write-GodLog "Received start request: $($script:GodExperiment) / experiment_$($script:GodExperimentRun)"
}

function Wait-ForStartRequest {
  Write-GodLog "Waiting for setup wizard to save and request startup"
  $nextNotice = (Get-Date).AddSeconds(30)
  while (-not (Test-Path $script:StartRequestFile)) {
    Start-Sleep -Seconds 2
    if ((Get-Date) -ge $nextNotice) {
      Write-GodLog "Still waiting on $(Get-SetupUrl)"
      $nextNotice = (Get-Date).AddSeconds(30)
    }
  }
  Receive-StartRequest
}

function Start-WithSetupIfNeeded {
  Ensure-Prerequisites
  Load-Env
  if (Test-PendingStartRequest) {
    Write-GodLog "Applying pending setup startup request"
    Receive-StartRequest
    Remove-ProcessEnv "GOD_SETUP_MODE"
    Stop-All
    Start-All
    return
  }
  if (Test-ReadyStartConfig) {
    Start-All
    return
  }

  Write-GodLog "No complete experiment configuration found; starting setup wizard first"
  Start-SetupServices
  Wait-ForStartRequest
  Remove-ProcessEnv "GOD_SETUP_MODE"
  Stop-ControlServices
  Start-All
}

function Configure-Experiment {
  Ensure-Prerequisites
  Write-GodLog "Starting new experiment setup wizard"
  Start-SetupServices
  Wait-ForStartRequest
  Remove-ProcessEnv "GOD_SETUP_MODE"
  Stop-ControlServices
  Start-All
}

function New-LiveSession {
  if (-not (Test-BackendHealthy)) {
    Start-Backend
  }
  Write-GodLog "Creating live session"
  try {
    $statusJson = Invoke-RestMethod -Method Post -Uri (Get-SessionUrl) -ContentType "application/json" -Body "{}"
  } catch {
    Stop-God "Failed to create live session"
  }
  $stepCount = if ($statusJson.PSObject.Properties["step_count"]) { [int]$statusJson.step_count } else { 0 }
  if ((Get-EnvValue "GOD_PRIME_FIRST_STEP" "1") -ne "0" -and $stepCount -eq 0) {
    Write-GodLog "Priming live session (step 1)"
    try {
      Invoke-RestMethod -Method Post -Uri (Get-RunStepUrl) -ContentType "application/json" -Body "{}" | Out-Null
    } catch {
      Stop-God "Failed to run the first live step"
    }
  }
}

function Start-All {
  Load-Env
  Require-CurrentExperimentConfig
  Setup-Dependencies
  Ensure-EnvFile
  Prepare-Experiment
  Start-Runtime
  Start-Backend
  Start-Frontend
  New-LiveSession
  Show-Status
}

function Restart-All {
  Ensure-Prerequisites
  Stop-All
  Start-WithSetupIfNeeded
}

function Start-NewRun {
  Ensure-Prerequisites
  Load-Env
  Require-CurrentExperimentConfig
  Set-ProcessEnv "GOD_SESSION_PREFIX" "$($script:GodExperiment)_fresh_$((Get-Date).ToString('yyyyMMdd_HHmmss'))"
  Stop-All
  $runDir = Join-PathMany $script:LiveWorkspacePath "hypothesis_$($script:GodExperiment)" "experiment_$($script:GodExperimentRun)" "run"
  Write-GodLog "New run will clear: $runDir"
  Remove-Item $runDir -Recurse -Force -ErrorAction SilentlyContinue
  Write-GodLog "Cleared previous run"
  Start-All
}

function Show-PortStatus {
  param(
    [string]$Label,
    [int]$Port
  )
  if (Test-PortOpen $Port) {
    "{0,-24} {1} up" -f $Label, $Port | Write-Host
  } else {
    "{0,-24} {1} down" -f $Label, $Port | Write-Host
  }
}

function Show-Status {
  Load-Env
  Write-Host ""
  Write-Host "GOD status"
  Write-Host "----------"
  Show-PortStatus "Backend" $script:GodBackendPort
  Show-PortStatus "Control room" $script:GodFrontendPort
  Show-PortStatus "Agent runtime" $script:RuntimeAgentPort
  Show-PortStatus "Agent runtime web" $script:RuntimeWebPort
  Show-PortStatus "Agent runtime gateway" $script:RuntimeGatewayPort
  Show-PortStatus "Agent runtime UI" $script:RuntimeUiPort
  Write-Host ""
  Write-Host "URLs"
  Show-FrontendLinks
  Write-Host ("Backend:          {0}/health" -f $script:BackendUrl)
  Write-Host ""
  Write-Host "Current experiment"
  if (Test-CurrentExperimentConfig) {
    Write-Host ("Experiment:     {0} / experiment_{1}" -f $script:GodExperiment, $script:GodExperimentRun)
    Write-Host ("Workspace:      {0}" -f $script:LiveWorkspacePath)
  } else {
    Write-Host "Experiment:     <not configured>"
  }
  Write-Host ""
  Write-Host "Model"
  Write-Host ("API key:       {0}" -f (Get-ConfiguredState (Get-EnvValue "GOD_LLM_API_KEY" "")))
  Write-Host ("API base:      {0}" -f (Get-EnvValue "GOD_LLM_API_BASE" "<unset>"))
  Write-Host ("Model:         {0}" -f (Get-EnvValue "GOD_LLM_MODEL" "<unset>"))
}

function Watch-Logs {
  foreach ($logPath in @($script:RuntimeLog, $script:BackendLog, $script:FrontendLog)) {
    if (-not (Test-Path $logPath)) {
      Write-TextUtf8NoBom $logPath ""
    }
  }
  Get-Content $script:RuntimeLog, $script:BackendLog, $script:FrontendLog -Wait
}

function Open-Replay {
  Load-Env
  if (-not (Test-CurrentExperimentConfig)) {
    Open-SetupPage
    return
  }
  Open-FrontendPages
}

function Show-InteractiveMenu {
  @"

GOD - Govern, Observe, Direct

1. Start
2. Restart
3. New run (reset replay and start fresh)
4. Configure new experiment
5. Status
6. Stop
7. Tail logs
8. Setup dependencies only

"@ | Write-Host
  $choice = Read-Host "Choose"
  switch ($choice) {
    "1" { Start-WithSetupIfNeeded }
    "" { Start-WithSetupIfNeeded }
    "2" { Restart-All }
    "3" { Start-NewRun }
    "4" { Configure-Experiment; Open-FrontendPages }
    "5" { Show-Status }
    "6" { Stop-All }
    "7" { Watch-Logs }
    "8" { Setup-Dependencies; Set-ProcessEnv "GOD_SETUP_MODE" "1"; Ensure-EnvFile }
    default { Show-Usage; exit 2 }
  }
}

Load-Env

switch ($Action) {
  "menu" { Show-InteractiveMenu }
  "setup" { Setup-Dependencies; Set-ProcessEnv "GOD_SETUP_MODE" "1"; Ensure-EnvFile }
  "configure" { Configure-Experiment; Open-FrontendPages }
  "start" { Start-WithSetupIfNeeded; Open-FrontendPages }
  "restart" { Restart-All; Open-FrontendPages }
  "new-run" { Start-NewRun; Open-FrontendPages }
  "factory-reset" { Reset-Factory }
  "reset" { Reset-Factory }
  "session" { Ensure-Prerequisites; Prepare-Experiment; New-LiveSession }
  "stop" { Stop-All }
  "status" { Show-Status }
  "tail" { Watch-Logs }
  "open" { Open-Replay }
  "-h" { Show-Usage }
  "--help" { Show-Usage }
  "help" { Show-Usage }
  default { Show-Usage; exit 2 }
}
