param(
  [string]$WsUrl = "ws://127.0.0.1:8765",
  [int]$DurationSec = 1800,
  [string]$OutBase = "runs",
  [string]$RunId = "",
  [string]$Types = "",           # 为空表示全量录制；例如 "status,result,vision,exec"
  [string]$Token = "",           # 对应后端 AUTH_TOKEN（可选）
  [string]$Ffmpeg = "ffmpeg",
  [double]$Fps = 15,
  [int]$Crf = 23,
  [string]$Preset = "veryfast",
  [int]$SegmentSec = 600,
  [string[]]$Streams = @()       # 例如: "rear=http://127.0.0.1:8765/proxy/robot/mjpg?port=8000&path=/stream.mjpg"
)

$ErrorActionPreference = "Stop"

function New-RunId() {
  return (Get-Date).ToString("yyyyMMdd_HHmmss")
}

if (-not $RunId) { $RunId = New-RunId }
$runDir = Join-Path $OutBase $RunId
$videoDir = Join-Path $runDir "video"
New-Item -ItemType Directory -Force -Path $videoDir | Out-Null

Write-Host "[capture] runDir=$runDir"
Write-Host "[capture] wsUrl=$WsUrl durationSec=$DurationSec"

# 解析 Streams：label=url
$labels = @()
$urls = @()
foreach ($s in $Streams) {
  if (-not $s) { continue }
  $idx = $s.IndexOf("=")
  if ($idx -lt 1) { throw "Invalid -Streams item (expected label=url): $s" }
  $labels += $s.Substring(0, $idx).Trim()
  $urls += $s.Substring($idx + 1).Trim()
}

if ($urls.Count -eq 0) {
  Write-Host "[capture] 未传 -Streams，将只录 WS 日志（不录视频）"
}

$wsOut = Join-Path $runDir "ws.jsonl"

$wsArgs = @("scripts\\record_ws.py", $WsUrl, "--out", $wsOut)
if ($Types) { $wsArgs += @("--types", $Types) }
if ($Token) { $wsArgs += @("--token", $Token) }
if ($DurationSec -gt 0) { $wsArgs += @("--duration-sec", "$DurationSec") }

Write-Host "[capture] start ws recorder -> $wsOut"
$wsProc = Start-Process -FilePath "python" -ArgumentList $wsArgs -PassThru -NoNewWindow

$vidProc = $null
if ($urls.Count -gt 0) {
  $vidArgs = @(
    "scripts\\record_mjpeg.py",
    "--out-dir", $videoDir,
    "--ffmpeg", $Ffmpeg,
    "--fps", "$Fps",
    "--crf", "$Crf",
    "--preset", $Preset,
    "--segment-sec", "$SegmentSec"
  )
  if ($DurationSec -gt 0) { $vidArgs += @("--duration-sec", "$DurationSec") }
  for ($i=0; $i -lt $urls.Count; $i++) {
    $vidArgs += @("--label", $labels[$i], "--url", $urls[$i])
  }
  Write-Host "[capture] start mjpeg recorder -> $videoDir"
  $vidProc = Start-Process -FilePath "python" -ArgumentList $vidArgs -PassThru -NoNewWindow
}

try {
  if ($DurationSec -gt 0) {
    $deadline = (Get-Date).AddSeconds($DurationSec)
    while ((Get-Date) -lt $deadline) {
      Start-Sleep -Milliseconds 500
      if ($wsProc.HasExited) { break }
      if ($vidProc -and $vidProc.HasExited) { break }
    }
  } else {
    Write-Host "[capture] DurationSec=0，按 Ctrl+C 结束"
    while ($true) { Start-Sleep -Seconds 1 }
  }
} finally {
  foreach ($p in @($vidProc, $wsProc)) {
    if ($p -and -not $p.HasExited) {
      try { Stop-Process -Id $p.Id -Force } catch {}
    }
  }
}

Write-Host "[capture] analyze run..."
python scripts\\analyze_run.py $runDir | Out-Host
Write-Host "[capture] done: $runDir"
