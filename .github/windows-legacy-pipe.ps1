$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:UV_PYTHON = '3.11'
$tokens = $null
$parseErrors = $null
$source = (Resolve-Path -LiteralPath 'src/scripts/god.ps1').Path
$ast = [System.Management.Automation.Language.Parser]::ParseFile($source, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -ne 0) { throw "Could not parse god.ps1: $parseErrors" }
$definition = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Invoke-NativeCommand' }, $true)
if ($null -eq $definition) { throw 'Invoke-NativeCommand was not found' }
. ([ScriptBlock]::Create($definition.Extent.Text))
$probeFile = Join-Path $env:RUNNER_TEMP 'god-stdin-probe.py'
Set-Content -LiteralPath $probeFile -Encoding Ascii -Value 'import sys; data = sys.stdin.buffer.read(); print(f"stdin={data!r}"); print(f"first line={data.splitlines()[:1]!r}")'
$log = Join-Path $env:RUNNER_TEMP 'god-stdin-probe.log'
$uv = (Get-Command uv.exe).Source
$python = (Get-Command python.exe).Source
Write-Host "PowerShell: $($PSVersionTable.PSVersion), pipeline output encoding: $($OutputEncoding.WebName)"
$selectionWithLF = "en`n"
$selectionNoLF = 'en'
$selectionAsCRLF = "en`r`n"
Write-Host 'Direct Windows PowerShell pipeline to python.exe, en + LF'
$selectionWithLF | & $python $probeFile
Write-Host 'Direct Windows PowerShell pipeline to uv.exe, en + LF'
$selectionWithLF | & $uv run --no-project python $probeFile
foreach ($choice in @($selectionWithLF, $selectionNoLF, $selectionAsCRLF, "yes`nen`n")) {
  Write-Host "Product Invoke-NativeCommand to uv.exe, synthetic choice length $($choice.Length)"
  Remove-Item -LiteralPath $log -ErrorAction SilentlyContinue
  $choice | Invoke-NativeCommand -FilePath $uv -ArgumentList @('run', '--no-project', 'python', $probeFile) -LogPath $log
  if ($LASTEXITCODE -ne 0) { throw "Probe exited $LASTEXITCODE" }
  Get-Content -LiteralPath $log -Encoding UTF8 | Write-Host
}
