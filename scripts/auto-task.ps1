<#
Tự động hoá nhiều task liên tiếp: Codex code → kiểm tra → Claude Code review → Codex sửa → CI → merge + push.

Ví dụ:
  .\scripts\auto-task.ps1 -Tasks T03                 # một task
  .\scripts\auto-task.ps1 -Tasks T03,T04             # danh sách
  .\scripts\auto-task.ps1 -From T05 -To T18          # một dải task
  .\scripts\auto-task.ps1 -Tasks T03 -NoMerge        # làm + review, không merge
  .\scripts\auto-task.ps1 -Tasks T02 -SkipImplement  # task đã code xong, chỉ review/sửa/merge

Điểm dừng an toàn (mặc định):
  - Task nhạy cảm ($ApproveBeforeMerge): làm và review xong thì dừng, chờ bạn tự merge.
  - Cuối mốc ($Milestones): merge xong thì dừng để bạn dùng thử trước khi chạy tiếp.
  - Task blocked, kiểm tra lỗi, CI đỏ, hoặc hết số vòng sửa: dừng ngay.
  Bỏ qua các điểm dừng mốc bằng -IgnoreMilestones (không bỏ qua được task nhạy cảm).

Màn hình chỉ hiện các dòng trạng thái; toàn bộ output của Codex/Claude nằm trong file log
(var/auto-task/). Muốn xem trực tiếp khi chạy, thêm -ShowAgentOutput.

Yêu cầu: codex và claude CLI đã đăng nhập; Docker đang chạy; repo sạch.
Khuyên dùng GitHub CLI để đợi CI:  winget install GitHub.cli ; gh auth login
Kiểm tra cờ CLI trên máy bạn:  codex exec --help ; claude --help
#>
param(
  [string[]]$Tasks,
  [string]$From,
  [string]$To,
  [int]$MaxRounds = 3,
  [switch]$NoMerge,
  [switch]$SkipImplement,
  [switch]$IgnoreMilestones,
  [switch]$ShowAgentOutput
)
# 'Continue': git/gh ghi tiến trình ra stderr; Windows PowerShell 5.1 coi đó là lỗi nếu đặt 'Stop'.
# Mọi lỗi thật được kiểm tra bằng `$LASTEXITCODE và dừng bằng throw.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$ApproveBeforeMerge = @('T04', 'T05', 'T23', 'T24', 'T29')
$Milestones = @('T04', 'T18', 'T21', 'T24', 'T28', 'T33')

# ---------- Danh sách task ----------
if ($From -and $To) {
  $a = [int]($From -replace '\D', ''); $b = [int]($To -replace '\D', '')
  $Tasks = $a..$b | ForEach-Object { 'T{0:D2}' -f $_ }
}
if (-not $Tasks) { throw 'Cần -Tasks T03,T04 hoặc -From T03 -To T06' }
$Tasks = $Tasks | ForEach-Object { $_.Trim().ToUpper() }
foreach ($t in $Tasks) {
  if (-not (Get-ChildItem -Path (Join-Path $root 'tasks') -Filter "$t-*.md")) { throw "Không có file task cho $t" }
}

# ---------- Kiểm tra công cụ trước khi chạy ----------
$missing = @()
$install = @{
  codex  = 'winget install OpenAI.Codex   (hoặc: npm install -g @openai/codex), rồi chạy: codex login'
  claude = 'winget install Anthropic.ClaudeCode, mở PowerShell mới, chạy: claude   (đăng nhập lần đầu)'
  git    = 'winget install Git.Git'
  docker = 'Cài Docker Desktop và mở nó lên'
  uv     = 'winget install astral-sh.uv'
}
foreach ($tool in @('codex', 'claude', 'git', 'docker', 'uv')) {
  if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { $missing += "  - $tool : $($install[$tool])" }
}
if ($missing) {
  Write-Host "Thiếu công cụ, chưa chạy gì cả:`n$($missing -join "`n")`nCài xong thì mở PowerShell mới rồi chạy lại." -ForegroundColor Red
  exit 3
}

$logDir = Join-Path $root 'var/auto-task'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ('run-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')
function Say($msg, $color = 'Cyan') {
  $line = "[$(Get-Date -Format 'HH:mm:ss')] $msg"
  Write-Host $line -ForegroundColor $color
  Add-Content -Path $log -Value $line -Encoding utf8
}
# Ghi output của lệnh ngoài vào log (dạng chữ thường, không có "RemoteException"),
# chỉ in ra màn hình khi có -ShowAgentOutput.
function Write-ToolOutput {
  param([Parameter(ValueFromPipeline = $true)]$Line)
  process {
    $text = "$Line"
    Add-Content -Path $log -Value $text -Encoding utf8
    if ($ShowAgentOutput) { Write-Host $text -ForegroundColor DarkGray }
  }
}
function Invoke-Git { git @args 2>&1 | ForEach-Object { Add-Content -Path $log -Value "$_" -Encoding utf8 }; if ($LASTEXITCODE -ne 0) { throw "git $($args -join ' ') lỗi. Xem $log" } }

function Assert-Clean([string]$why) {
  $dirty = git status --porcelain
  if ($dirty) { throw "$why`nRepo còn thay đổi chưa commit:`n$dirty" }
}

function Sync-Main {
  Invoke-Git switch main
  Invoke-Git pull --ff-only
}

function Invoke-Codex([string]$prompt) {
  Say "Codex: $prompt"
  # CLI hiện tại dùng sandbox workspace-write và xét yêu cầu cấp quyền tự động.
  $prompt | codex exec --approve-for-me -C $root - 2>&1 | Write-ToolOutput
  if ($LASTEXITCODE -ne 0) { throw "Codex lỗi (exit $LASTEXITCODE). Xem $log" }
  Say "  Codex xong (chi tiết trong log)." 'DarkGray'
}

function Invoke-ClaudeReview([string]$task) {
  Say "Claude Code: Review $task"
  claude -p "Review $task following tasks/_review.md exactly." --permission-mode acceptEdits `
    --allowedTools "Read,Grep,Glob,Write,Bash" 2>&1 | Write-ToolOutput
  if ($LASTEXITCODE -ne 0) { throw "Claude Code lỗi (exit $LASTEXITCODE). Xem $log" }
  $changed = git status --porcelain | Where-Object { $_ -notmatch "tasks/reviews/$task\.md" }
  if ($changed) { throw "Reviewer đã sửa file ngoài báo cáo, dừng lại để bạn kiểm tra:`n$changed" }
}

function Get-Verdict([string]$task) {
  $report = Join-Path $root "tasks/reviews/$task.md"
  if (-not (Test-Path $report)) { throw "Không thấy báo cáo $report" }
  $m = Select-String -Path $report -Pattern '\*\*Verdict:\*\*\s*(APPROVE WITH NITS|APPROVE|CHANGES REQUIRED)' | Select-Object -First 1
  if (-not $m) { throw "Báo cáo review $task không có dòng Verdict hợp lệ" }
  return $m.Matches[0].Groups[1].Value
}

function Get-Status([string]$task) {
  $m = Select-String -Path (Join-Path $root 'tasks/PROGRESS.md') -Pattern "^\|\s*$task\s*\|\s*([a-z]+)" | Select-Object -First 1
  if ($m) { return $m.Matches[0].Groups[1].Value } else { return 'todo' }
}

function Set-StatusDone([string]$task) {
  $path = Join-Path $root 'tasks/PROGRESS.md'
  $text = [IO.File]::ReadAllText($path)
  $new = [regex]::Replace($text, "(?m)^(\|\s*$task\s*\|\s*)[a-z]+", '${1}done')
  [IO.File]::WriteAllText($path, $new, [System.Text.UTF8Encoding]::new($false))
}

function Invoke-Checks {
  # Kiểm tra độc lập trên máy, không dựa vào lời báo cáo của agent.
  Say 'Kiểm tra độc lập trên máy'
  $ok = $true
  docker compose up -d db redis mailpit 2>&1 | Out-Null
  $groups = @()
  if (Test-Path 'backend/pyproject.toml') {
    $groups += , @('backend', @('uv run pytest -q', 'uv run ruff check .', 'uv run ruff format --check .', 'uv run mypy app'))
  }
  if (Test-Path 'frontend/package.json') {
    $groups += , @('frontend', @('npm run lint', 'npm run typecheck', 'npx vitest run'))
  }
  foreach ($g in $groups) {
    Push-Location $g[0]
    foreach ($cmd in $g[1]) {
      Invoke-Expression "$cmd 2>&1" | ForEach-Object { Add-Content -Path $log -Value "$_" -Encoding utf8 }
      if ($LASTEXITCODE -ne 0) { Say "  LỖI: $($g[0]) > $cmd" 'Red'; $ok = $false } else { Say "  ok: $($g[0]) > $cmd" 'DarkGray' }
    }
    Pop-Location
  }
  return $ok
}

function Wait-CI([string]$branch) {
  Invoke-Git push -u origin $branch
  if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Say 'Không có GitHub CLI (gh): bỏ qua bước đợi CI. Nên cài để an toàn hơn.' 'Yellow'
    return $true
  }
  $sha = (git rev-parse HEAD).Trim()
  Say "Đợi CI trên GitHub cho $branch"
  $runId = $null
  for ($i = 0; $i -lt 30 -and -not $runId; $i++) {
    Start-Sleep -Seconds 10
    $runs = gh run list --branch $branch --limit 5 --json databaseId,headSha | ConvertFrom-Json
    $runId = ($runs | Where-Object { $_.headSha -eq $sha } | Select-Object -First 1).databaseId
  }
  if (-not $runId) { Say 'Không thấy lần chạy CI nào sau 5 phút.' 'Red'; return $false }
  gh run watch $runId --exit-status --interval 15 2>&1 | ForEach-Object { Add-Content -Path $log -Value "$_" -Encoding utf8 }
  return ($LASTEXITCODE -eq 0)
}

function Complete-Merge([string]$task, [string]$branch) {
  Sync-Main
  Invoke-Git merge --no-ff $branch -m "Merge ${task}"
  Set-StatusDone $task
  Invoke-Git add tasks/PROGRESS.md
  git diff --cached --quiet
  if ($LASTEXITCODE -ne 0) { Invoke-Git commit -m "${task}: mark done" }
  Invoke-Git push origin main
}

# Trả về: merged | approval | stopped
function Invoke-OneTask([string]$task) {
  Say "========== $task ==========" 'Magenta'
  if ((Get-Status $task) -eq 'done') { Say "$task đã done, bỏ qua."; return 'merged' }
  Assert-Clean "Không thể bắt đầu $task."

  if (-not $SkipImplement) {
    Sync-Main
    Invoke-Codex "Implement $task following tasks/_implement.md exactly."
    if ((Get-Status $task) -eq 'blocked') { Say "$task bị BLOCKED. Đọc tasks/PROGRESS.md." 'Red'; return 'stopped' }
    Assert-Clean 'Codex làm xong nhưng chưa commit hết.'
  }
  $branch = (git branch --show-current).Trim()
  if ($branch -eq 'main') { Say "Codex không tạo nhánh task cho $task." 'Red'; return 'stopped' }

  for ($round = 1; $round -le $MaxRounds; $round++) {
    Say "--- $task · vòng review $round ---"
    $checksOk = Invoke-Checks
    Invoke-ClaudeReview $task
    $verdict = Get-Verdict $task
    Say "Verdict: $verdict | Kiểm tra trên máy: $(if ($checksOk) {'PASS'} else {'FAIL'})"

    if ($verdict -like 'APPROVE*' -and $checksOk) {
      Invoke-Git add "tasks/reviews/$task.md"
      Invoke-Git commit -m "${task}: review approved"
      if (-not (Wait-CI $branch)) {
        Say "CI đỏ cho $task. Xem tab Actions trên GitHub." 'Red'
        if ($round -eq $MaxRounds) { return 'stopped' }
        Invoke-Codex "Fix $task following tasks/_fix.md. The review approved, but GitHub CI failed; run 'gh run view --log-failed' to see why and make CI pass."
        Assert-Clean 'Codex sửa xong nhưng chưa commit hết.'
        continue
      }
      if ($NoMerge) { Say "$task đạt (không merge vì -NoMerge). Nhánh: $branch" 'Green'; return 'approval' }
      if ($ApproveBeforeMerge -contains $task) {
        Say "$task đạt nhưng là task nhạy cảm: chờ bạn đọc diff rồi tự merge." 'Yellow'
        Write-Host "  git switch main; git merge --no-ff $branch; git push" -ForegroundColor Yellow
        Write-Host "  rồi đổi $task thành done trong tasks/PROGRESS.md" -ForegroundColor Yellow
        return 'approval'
      }
      Complete-Merge $task $branch
      Say "$task đã merge vào main và push." 'Green'
      return 'merged'
    }

    if ($round -eq $MaxRounds) { break }
    if ($verdict -like 'APPROVE*') {
      Invoke-Codex "Fix $task following tasks/_fix.md. The review approved, but the local checks failed; see $log. Make all checks in docs/specs/08-testing-quality.md pass."
    } else {
      Invoke-Codex "Fix $task following tasks/_fix.md exactly."
    }
    Assert-Clean 'Codex sửa xong nhưng chưa commit hết.'
  }
  Say "$task chưa đạt sau $MaxRounds vòng. Đọc tasks/reviews/$task.md." 'Red'
  return 'stopped'
}

# ---------- Chạy ----------
Say "Bắt đầu: $($Tasks -join ', '). Log: $log"
foreach ($task in $Tasks) {
  $result = Invoke-OneTask $task
  if ($result -ne 'merged') { Say "Dừng sau $task ($result)." 'Yellow'; exit 1 }
  if (-not $IgnoreMilestones -and ($Milestones -contains $task)) {
    Say "Xong mốc ở $task. Dừng để bạn dùng thử; chạy tiếp từ task sau khi sẵn sàng." 'Green'
    exit 0
  }
  $SkipImplement = $false
}
Say 'Hoàn tất toàn bộ danh sách task.' 'Green'
exit 0
