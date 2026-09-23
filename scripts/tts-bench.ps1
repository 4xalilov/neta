# Windows PowerShell: o'zbek TTS sinovi (Edge TTS, kalitsiz). Repo ildizidan ishga tushiring:
#   powershell -ExecutionPolicy Bypass -File scripts\tts-bench.ps1 [edge|edge,azure]
$ErrorActionPreference = "Stop"
$venv = "apps\api\.venv"
$py = "$venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
  if (Get-Command uv -ErrorAction SilentlyContinue) {
    uv venv --python 3.12 $venv
    uv pip install --python $py -e "apps\api[dev]"
  } else {
    Write-Host "uv topilmadi — oddiy Python bilan davom etamiz (tavsiya: irm https://astral.sh/uv/install.ps1 | iex)"
    $base = $null
    foreach ($cand in @("py -3.12", "py -3.13", "py -3.11", "python")) {
      try {
        $parts = $cand.Split(" ")
        $v = & $parts[0] $parts[1..($parts.Length-1)] -c "import sys; print(sys.version_info[:2] >= (3, 11))" 2>$null
        if ($v -eq "True") { $base = $cand; break }
      } catch {}
    }
    if (-not $base) { throw "Python 3.11+ topilmadi. https://www.python.org/downloads/ dan o'rnating (Add to PATH belgilang) yoki uv o'rnating." }
    $parts = $base.Split(" ")
    & $parts[0] $parts[1..($parts.Length-1)] -m venv $venv
    & $py -m pip install --upgrade pip
    & $py -m pip install -e "apps\api[dev]"
  }
}

$providers = if ($args.Count -gt 0) { $args[0] } else { "edge" }
& $py evals\tts_bench.py --providers $providers --out evals\out
Write-Host "Natija: evals\out\results.md va evals\out\edge_*.mp3"
