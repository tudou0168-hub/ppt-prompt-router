param(
  [Parameter(Mandatory=$true)][string]$BundleRoot,
  [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$env:PYTHONDONTWRITEBYTECODE = "1"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
chcp 65001 | Out-Null

function Invoke-PythonStrict {
  param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)
  & $Python @Arguments
  if ($LASTEXITCODE -ne 0) { throw "Python failed with exit code $LASTEXITCODE" }
}

$Work = Join-Path ([System.IO.Path]::GetTempPath()) ("PPT Director 中文 " + [guid]::NewGuid())
$Skills = Join-Path $Work "skills"
$Projects = Join-Path $Work "projects"
$Input = Join-Path $Work "测试材料.md"
New-Item -ItemType Directory -Force -Path $Skills,$Projects | Out-Null
Set-Content -Encoding UTF8 -Path $Input -Value "# 测试材料`n2026年启动公共服务优化。"

try {
  if (-not (Test-Path (Join-Path $BundleRoot "install.py"))) { throw "Root install.py is missing" }
  if ((Get-ChildItem -Path $BundleRoot -Filter install.py -Recurse).Count -ne 1) { throw "Bundle contains an ambiguous install.py" }

  Invoke-PythonStrict (Join-Path $BundleRoot "install.py") install --host generic --skills-dir $Skills
  Invoke-PythonStrict (Join-Path $BundleRoot "install.py") validate --host generic --skills-dir $Skills

  $Route = Join-Path $Skills "ppt-prompt-router\scripts\route.py"
  Invoke-PythonStrict $Route start --request "面向政府领导汇报公共服务规划，4页" --source $Input --page-count 4 --audience "政府领导" --prompt-id government_strategy --template-intent none --project-base $Projects --project-name windows_clean

  Invoke-PythonStrict (Join-Path $BundleRoot "install.py") upgrade --host generic --skills-dir $Skills
  Invoke-PythonStrict (Join-Path $BundleRoot "install.py") rollback --host generic --skills-dir $Skills
  Invoke-PythonStrict (Join-Path $BundleRoot "install.py") uninstall --host generic --skills-dir $Skills --yes
  Write-Output '{"status":"WINDOWS_CLEAN_ROOM_PASSED"}'
}
finally {
  if (Test-Path $Work) { Remove-Item -Recurse -Force $Work }
}
