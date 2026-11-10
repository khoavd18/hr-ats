<#
Tự động hoá nhiều task liên tiếp: Codex code → kiểm tra → review (mặc định Codex, phiên riêng) → Codex sửa → CI → merge + push.

Ví dụ:
  .\scripts\auto-task.ps1 -Tasks T03                 # một task
  .\scripts\auto-task.ps1 -Tasks T03,T04             # danh sách
  .\scripts\auto-task.ps1 -From T05 -To T18          # một dải task
  .\scripts\auto-task.ps1 -Tasks T03 -NoMerge        # làm + review, không merge
  .\scripts\auto-task.ps1 -Tasks T02 -SkipImplement  # task đã code xong, chỉ review/sửa/merge

Mặc định script tự merge mọi task đạt review + kiểm tra trên máy + CI.
Luôn dừng khi: task blocked, kiểm tra lỗi, CI đỏ, hoặc hết số vòng sửa.
Điểm dừng tuỳ chọn:
  -RequireApproval   task nhạy cảm ($ApproveBeforeMerge) làm + review xong thì dừng, chờ bạn merge.
  -StopAtMilestones  dừng sau mỗi mốc ($Milestones) để dùng thử.

Reviewer: -Reviewer codex (mặc định, phiên Codex mới, chỉ được ghi báo cáo) hoặc -Reviewer claude.
  -ReviewModel <tên> chọn model cho reviewer (nên khác model code, vd. model mạnh hơn).

Hiển thị (-Output):
  compact (mặc định): mỗi bước một dòng: Codex nói gì, chạy lệnh nào, sửa file nào, lệnh nào lỗi,
                      và các phát hiện của review. Bỏ qua nội dung file, diff, output dài.
  full:               in toàn bộ output của Codex/Claude (rất dài).
  quiet:              chỉ các dòng trạng thái của script.
Toàn bộ output luôn được ghi vào file log trong var/auto-task/.

Model: script in ra model Codex và Claude thực tế dùng ở mỗi bước.
Chọn model: -CodexModel <tên> (truyền cho codex exec -m), -ClaudeModel <tên> (truyền cho claude --model).

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
  [switch]$IgnoreMilestones,  # giữ cho tương thích; giờ mặc định không dừng ở mốc
  [switch]$RequireApproval,
  [switch]$StopAtMilestones,
  [ValidateSet('codex', 'claude')][string]$Reviewer = 'codex',
  [string]$ReviewModel,
  [ValidateSet('compact', 'full', 'quiet')][string]$Output = 'compact',
  [switch]$ShowAgentOutput,  # giữ cho tương thích: tương đương -Output full
  [string]$CodexModel,       # vd. -CodexModel gpt-6.1-sol (để trống: mặc định của Codex)
  [string]$ClaudeModel       # vd. -ClaudeModel opus hoặc sonnet (để trống: mặc định của Claude Code)
)
if ($ShowAgentOutput) { $Output = 'full' }
# 'Continue': git/gh ghi tiến trình ra stderr; Windows PowerShell 5.1 coi đó là lỗi nếu đặt 'Stop'.
# Mọi lỗi thật được kiểm tra bằng `$LASTEXITCODE và dừng bằng throw.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$ApproveBeforeMerge = if ($RequireApproval) { @('T04', 'T05', 'T23', 'T24', 'T29') } else { @() }
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
$needed = @('codex', 'git', 'docker', 'uv'); if ($Reviewer -eq 'claude') { $needed += 'claude' }
foreach ($tool in $needed) {
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
# ---------- Hiển thị output của agent ----------
# Mọi dòng đều vào log. Màn hình tuỳ -Output; chế độ compact đọc cấu trúc output của
# `codex exec` (các mốc: codex / exec / apply patch / exited N / web search / tokens used).
$script:fmt = @{ State = ''; Count = 0 }
function Get-Short([string]$text, [int]$max = 110) {
  $t = ($text -replace '\s+', ' ').Trim()
  if ($t.Length -gt $max) { $t = $t.Substring(0, $max - 1) + '…' }
  return $t
}
function Show([string]$text, $color = 'Gray') { Write-Host "    $text" -ForegroundColor $color }
function Format-Command([string]$line) {
  $c = $line -replace '^"[^"]*powershell(\.exe)?"\s+-Command\s+', ''
  $c = $c -replace '\s+in\s+[A-Za-z]:\\\S*\s*$', ''
  $c = $c.Trim().Trim("'").Trim('"')
  return Get-Short $c 100
}
function Format-CodexLine([string]$text) {
  $t = $text.Trim()
  switch -Regex ($t) {
    '^codex$' { $script:fmt.State = 'msg'; $script:fmt.Count = 0; return }
    '^exec$' { $script:fmt.State = 'exec'; return }
    '^apply patch$' { $script:fmt.State = 'patch'; return }
    '^(user|thinking)$' { $script:fmt.State = 'skip'; return }
    '^model:\s*(.+)$' { $script:codexModel = $Matches[1]; return }
    '^reasoning effort:\s*(.+)$' { Show "model: $($script:codexModel) · reasoning: $($Matches[1])" 'Magenta'; return }
    '^tokens used' { $script:fmt.State = 'tokens'; return }
    '^web search:\s*(.+)$' { Show "? tìm: $(Get-Short $Matches[1] 100)" 'DarkGray'; return }
    '^web search:\s*$' { return }
    '^exited (\d+) in' { Show "! lệnh lỗi (exit $($Matches[1])), Codex sẽ tự xử lý" 'Yellow'; $script:fmt.State = 'out'; return }
    '^succeeded in' { $script:fmt.State = 'out'; return }
  }
  switch ($script:fmt.State) {
    'msg' {
      if ($t -eq '') { if ($script:fmt.Count -gt 0) { $script:fmt.State = 'out' }; return }
      if ($script:fmt.Count -lt 4) { Show "* $(Get-Short $t 150)" 'White' }
      elseif ($script:fmt.Count -eq 4) { Show '  …' 'DarkGray' }
      $script:fmt.Count++
    }
    'exec' { if ($t) { Show "> $(Format-Command $t)" 'DarkCyan'; $script:fmt.State = 'out' } }
    'patch' {
      if ($t -match '^[A-Za-z]:\\') { Show "~ sửa: $((($t -replace [regex]::Escape("$root\"), '') -replace '\\', '/'))" 'Green' }
      elseif ($t -match '^diff ') { $script:fmt.State = 'out' }
    }
    'tokens' { if ($t) { Show "tokens: $t" 'DarkGray'; $script:fmt.State = 'out' } }
  }
}
function Format-ClaudeLine([string]$text) {
  $t = $text.Trim()
  if ($t -match '\[(BLOCKER|MAJOR|MINOR)\]') {
    $color = @{ BLOCKER = 'Red'; MAJOR = 'Yellow'; MINOR = 'DarkGray' }[$Matches[1]]
    Show "- $(Get-Short ($t -replace '^[-*]\s*', '') 150)" $color
  }
}
function Write-ToolOutput {
  param([Parameter(ValueFromPipeline = $true)]$Line, [ValidateSet('codex', 'claude', 'plain')][string]$Kind = 'plain')
  begin { $script:fmt.State = ''; $script:fmt.Count = 0; $script:recent = [System.Collections.Generic.List[string]]::new() }
  process {
    $text = "$Line"
    $script:recent.Add($text); if ($script:recent.Count -gt 40) { $script:recent.RemoveAt(0) }
    Add-Content -Path $log -Value $text -Encoding utf8
    if ($Output -eq 'full') { Write-Host $text -ForegroundColor DarkGray }
    elseif ($Output -eq 'compact') {
      if ($Kind -eq 'codex') { Format-CodexLine $text }
      # Phát hiện của reviewer được in từ file báo cáo (Show-Findings), không in ở đây.
    }
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

# Hết hạn mức của Codex/Claude: đọc giờ reset trong thông báo (vd. "resets 7:40pm"),
# chờ đến lúc đó rồi chạy lại. Trả về $true nếu đã chờ.
function Wait-IfLimited([string]$who) {
  $tail = ($script:recent -join "`n")
  if ($tail -notmatch '(?i)(hit your .{0,30}limit|usage limit|rate.?limit|limit reached|quota exceeded)') { return $false }
  $wait = 15
  $now = Get-Date
  $inv = [Globalization.CultureInfo]::InvariantCulture
  if ($tail -match '(?i)try again (?:at|after)\s+([A-Za-z]{3,9}\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4},?\s+\d{1,2}:\d{2}\s*[AP]M)') {
    # Codex: "try again at Nov 9th, 2026 1:09 AM"
    $raw = ($Matches[1] -replace '(?i)(\d)(st|nd|rd|th)', '$1') -replace ',', '' -replace '\s+', ' '
    try { $wait = [math]::Ceiling(([datetime]::Parse($raw, $inv) - $now).TotalMinutes) + 2 } catch { $wait = 15 }
  } elseif ($tail -match '(?i)resets?\s+(?:at\s+)?(\d{1,2}(?::\d{2})?\s*[ap]\.?m)') {
    # Claude Code: "resets 7:40pm (Asia/Saigon)"
    try {
      $at = $now.Date + [datetime]::Parse(($Matches[1] -replace '\.', '').ToUpper(), $inv).TimeOfDay
      if ($at -lt $now) { $at = if (($now - $at).TotalHours -lt 12) { $now } else { $at.AddDays(1) } }
      $wait = [math]::Ceiling(($at - $now).TotalMinutes) + 2
    } catch { $wait = 15 }
  }
  $wait = [math]::Max(2, [math]::Min($wait, 8 * 60))
  Say "$who hết hạn mức sử dụng. Chờ $wait phút (đến khoảng $((Get-Date).AddMinutes($wait).ToString('HH:mm'))) rồi chạy lại. Có thể để máy chạy, đừng tắt cửa sổ." 'Yellow'
  Start-Sleep -Seconds ($wait * 60)
  return $true
}

function Invoke-Codex([string]$prompt) {
  Say "Codex: $prompt"
  for ($attempt = 1; $attempt -le 8; $attempt++) {
    # CLI hiện tại dùng sandbox workspace-write và xét yêu cầu cấp quyền tự động.
    $modelArgs = @(); if ($CodexModel) { $modelArgs = @('-m', $CodexModel) }
    $prompt | codex exec --approve-for-me @modelArgs -C $root - 2>&1 | Write-ToolOutput -Kind codex
    if ($LASTEXITCODE -eq 0) { Say "  Codex xong (chi tiết trong log)." 'DarkGray'; return }
    if (-not (Wait-IfLimited 'Codex')) { break }
    Say "Codex: chạy lại sau khi hết chờ: $prompt"
  }
  throw "Codex lỗi (exit $LASTEXITCODE). Xem $log"
}

function Invoke-ClaudeReview([string]$task) {
  Say "Claude Code: Review $task"
  for ($attempt = 1; $attempt -le 8; $attempt++) {
    $modelArgs = @(); if ($ClaudeModel) { $modelArgs = @('--model', $ClaudeModel) }
    # JSON để biết model thực tế; phần "result" (báo cáo review) vẫn được hiển thị và ghi log như văn bản.
    $raw = claude -p "Review $task following tasks/_review.md exactly." --permission-mode acceptEdits `
      --allowedTools "Read,Grep,Glob,Write,Bash" --output-format json @modelArgs 2>&1
    $code = $LASTEXITCODE
    $text = ($raw | ForEach-Object { "$_" }) -join "`n"
    $parsed = $null
    try { $parsed = $text.Substring([math]::Max(0, $text.IndexOf('{'))) | ConvertFrom-Json } catch { $parsed = $null }
    if ($parsed -and $parsed.PSObject.Properties['result']) {
      ("$($parsed.result)" -split "`r?`n") | Write-ToolOutput -Kind claude
      $models = @()
      if ($parsed.PSObject.Properties['modelUsage'] -and $parsed.modelUsage) { $models = @($parsed.modelUsage.PSObject.Properties.Name) }
      $cost = if ($parsed.PSObject.Properties['total_cost_usd']) { ' · ~$' + [math]::Round([double]$parsed.total_cost_usd, 2) } else { '' }
      if ($models) { Say "  Claude model: $($models -join ', ')$cost" 'Magenta' }
    } else {
      ($text -split "`r?`n") | Write-ToolOutput -Kind claude
    }
    $LASTEXITCODE = $code
    if ($code -eq 0) { break }
    if (-not (Wait-IfLimited 'Claude Code')) { throw "Claude Code lỗi (exit $LASTEXITCODE). Xem $log" }
    if ($attempt -eq 8) { throw "Claude Code vẫn hết hạn mức sau nhiều lần chờ. Xem $log" }
    Say "Claude Code: review lại $task sau khi hết chờ"
  }
  $changed = git status --porcelain | Where-Object { $_ -notmatch "tasks/reviews/$task\.md" }
  if ($changed) { throw "Reviewer đã sửa file ngoài báo cáo, dừng lại để bạn kiểm tra:`n$changed" }
}

function Invoke-CodexReview([string]$task) {
  Say "Codex (review, phiên mới): Review $task"
  $prompt = "Review $task following tasks/_review.md exactly. You are an independent reviewer in a fresh session: " +
    "you did not write this code, so do not trust tasks/PROGRESS.md or commit messages; verify every claim yourself by " +
    "reading the diff and running the checks. Write ONLY tasks/reviews/$task.md. Do not modify any other file, do not fix " +
    "the code, and do not commit."
  $env:GIT_OPTIONAL_LOCKS = '0'  # git chỉ đọc, không tạo file khoá
  for ($attempt = 1; $attempt -le 8; $attempt++) {
    $modelArgs = @(); if ($ReviewModel) { $modelArgs = @('-m', $ReviewModel) }
    $prompt | codex exec --approve-for-me @modelArgs -C $root - 2>&1 | Write-ToolOutput -Kind codex
    if ($LASTEXITCODE -eq 0) { break }
    if (-not (Wait-IfLimited 'Codex (review)')) { throw "Codex review lỗi (exit $LASTEXITCODE). Xem $log" }
    if ($attempt -eq 8) { throw "Codex vẫn hết hạn mức sau nhiều lần chờ. Xem $log" }
    Say "Codex: review lại $task sau khi hết chờ"
  }
  Remove-Item Env:GIT_OPTIONAL_LOCKS -ErrorAction SilentlyContinue
  $changed = git status --porcelain | Where-Object { $_ -notmatch "tasks/reviews/$task\.md" }
  if ($changed) { throw "Reviewer đã sửa file ngoài báo cáo, dừng lại để bạn kiểm tra:`n$changed" }
}

function Invoke-Review([string]$task) {
  if ($Reviewer -eq 'claude') { Invoke-ClaudeReview $task } else { Invoke-CodexReview $task }
  Show-Findings $task
}

# In các phát hiện từ file báo cáo (gọn, không phụ thuộc reviewer nào).
function Show-Findings([string]$task) {
  $report = Join-Path $root "tasks/reviews/$task.md"
  if (-not (Test-Path $report)) { return }
  $colors = @{ BLOCKER = 'Red'; MAJOR = 'Yellow'; MINOR = 'DarkGray' }
  # Báo cáo được ghi nối tiếp qua nhiều vòng: chỉ in phát hiện của vòng review mới nhất.
  $lines = @(Get-Content -Path $report -Encoding utf8)
  $start = 0
  for ($i = 0; $i -lt $lines.Count; $i++) { if ($lines[$i] -match '\*\*Verdict:\*\*') { $start = $i } }
  foreach ($raw in $lines[$start..($lines.Count - 1)]) {
    if ($raw -notmatch '\[(BLOCKER|MAJOR|MINOR)\]') { continue }
    $line = $raw.Trim() -replace '^[-*]\s*', ''
    if ($line -match '^\[(BLOCKER|MAJOR|MINOR)\]\s+F?\d|^\*\*\[(BLOCKER|MAJOR|MINOR)\]') {
      $level = if ($Matches[1]) { $Matches[1] } else { $Matches[2] }
      Show "- $(Get-Short $line 150)" $colors[$level]
    }
  }
}

function Get-Verdict([string]$task) {
  $report = Join-Path $root "tasks/reviews/$task.md"
  if (-not (Test-Path $report)) { throw "Không thấy báo cáo $report" }
  $m = Select-String -Path $report -Pattern '\*\*Verdict:\*\*\s*(APPROVE WITH NITS|APPROVE|CHANGES REQUIRED)' | Select-Object -Last 1
  # Nhiều vòng review ghi nối tiếp vào cùng file: verdict mới nhất là dòng cuối.
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

# Commit thay đổi Codex để lại (khi sandbox không cho Codex tự commit).
function Save-AgentWork([string]$task, [string]$what) {
  if (git status --porcelain) {
    Invoke-Git add -A
    Invoke-Git commit -m "${task}: $what"
    Say "  Đã commit thay đổi của Codex ($what)." 'DarkGray'
  }
}

# Trả về: merged | approval | stopped
function Invoke-OneTask([string]$task) {
  Say "========== $task ==========" 'Magenta'
  if ((Get-Status $task) -eq 'done') { Say "$task đã done, bỏ qua."; return 'merged' }
  Assert-Clean "Không thể bắt đầu $task."

  if (-not $SkipImplement) {
    Sync-Main
    # Script tự tạo nhánh: sandbox của Codex có thể không cho ghi vào .git.
    $taskFile = Get-ChildItem -Path (Join-Path $root 'tasks') -Filter "$task-*.md" | Select-Object -First 1
    $taskBranch = 'task/' + $taskFile.BaseName
    git show-ref --verify --quiet "refs/heads/$taskBranch"
    if ($LASTEXITCODE -eq 0) { Invoke-Git switch $taskBranch } else { Invoke-Git switch -c $taskBranch }
    Invoke-Codex "Implement $task following tasks/_implement.md exactly."
    if ((Get-Status $task) -eq 'blocked') { Say "$task bị BLOCKED. Đọc tasks/PROGRESS.md." 'Red'; return 'stopped' }
    Save-AgentWork $task 'implement'
    if (-not (git log --oneline "main..HEAD")) { Say "Codex không tạo thay đổi nào cho $task (có thể đang chờ bạn trả lời). Xem log." 'Red'; return 'stopped' }
  }
  $branch = (git branch --show-current).Trim()
  if ($branch -eq 'main') { Say "Codex không tạo nhánh task cho $task." 'Red'; return 'stopped' }

  for ($round = 1; $round -le $MaxRounds; $round++) {
    Say "--- $task · vòng review $round ---"
    $checksOk = Invoke-Checks
    Invoke-Review $task
    $verdict = Get-Verdict $task
    Say "Verdict: $verdict | Kiểm tra trên máy: $(if ($checksOk) {'PASS'} else {'FAIL'})"

    if ($verdict -like 'APPROVE*' -and $checksOk) {
      Invoke-Git add "tasks/reviews/$task.md"
      Invoke-Git commit -m "${task}: review approved"
      if (-not (Wait-CI $branch)) {
        Say "CI đỏ cho $task. Xem tab Actions trên GitHub." 'Red'
        if ($round -eq $MaxRounds) { return 'stopped' }
        Invoke-Codex "Fix $task following tasks/_fix.md. The review approved, but GitHub CI failed; run 'gh run view --log-failed' to see why and make CI pass."
        Save-AgentWork $task 'fix CI'
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
    Save-AgentWork $task 'fix review findings'
  }
  Say "$task chưa đạt sau $MaxRounds vòng. Đọc tasks/reviews/$task.md." 'Red'
  return 'stopped'
}

# ---------- Chạy ----------
Say "Bắt đầu: $($Tasks -join ', '). Log: $log"
foreach ($task in $Tasks) {
  $result = Invoke-OneTask $task
  if ($result -ne 'merged') { Say "Dừng sau $task ($result)." 'Yellow'; exit 1 }
  if ($StopAtMilestones -and ($Milestones -contains $task)) {
    Say "Xong mốc ở $task. Dừng để bạn dùng thử; chạy tiếp từ task sau khi sẵn sàng." 'Green'
    exit 0
  }
  $SkipImplement = $false
}
Say 'Hoàn tất toàn bộ danh sách task.' 'Green'
exit 0
