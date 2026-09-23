# Windows PowerShell: o'zbek TTS sinovi (Edge TTS, kalitsiz). Repo ildizidan ishga tushiring.
$ErrorActionPreference = "Stop"
if (-not (Test-Path "apps\api\.venv")) {
  uv venv --python 3.12 apps\api\.venv
  uv pip install --python apps\api\.venv\Scripts\python.exe -e "apps\api[dev]"
}
$providers = if ($args.Count -gt 0) { $args[0] } else { "edge" }
& apps\api\.venv\Scripts\python.exe evals\tts_bench.py --providers $providers --out evals\out
Write-Host "Natija: evals\out\results.md va evals\out\edge_*.mp3"
