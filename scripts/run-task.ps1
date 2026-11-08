<#
Giao một task trong tasks/ cho Codex CLI chạy không tương tác.
Ví dụ:  .\scripts\run-task.ps1 -Task T05
        .\scripts\run-task.ps1 -Task T05 -FullAuto     # cho Codex tự sửa file và chạy lệnh không hỏi
Kiểm tra cờ hiện có bằng:  codex exec --help
#>
param(
  [Parameter(Mandatory = $true)][string]$Task,
  [switch]$FullAuto,
  [switch]$NoBranch
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$file = Get-ChildItem -Path (Join-Path $root 'tasks') -Filter "$Task-*.md" | Select-Object -First 1
if (-not $file) { throw "Không tìm thấy file task cho $Task trong tasks/" }

if (-not $NoBranch -and (Test-Path (Join-Path $root '.git'))) {
  $branch = 'task/' + $file.BaseName
  git -C $root switch -c $branch 2>$null
  if ($LASTEXITCODE -ne 0) { git -C $root switch $branch }
}

$taskText = Get-Content -Raw -Encoding UTF8 $file.FullName
$prompt = @"
Bạn đang triển khai dự án hr-ats. Trước khi làm, đọc AGENTS.md, tasks/README.md và các spec được nêu trong task.
Làm đúng một task dưới đây theo quy trình trong tasks/README.md, đáp ứng Definition of Done trong docs/specs/08-testing-quality.md,
rồi cập nhật tasks/PROGRESS.md.

---- TASK: $($file.Name) ----
$taskText
"@

$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$codexArgs = @('exec', '-C', $root)
if ($FullAuto) { $codexArgs += '--full-auto' }
$codexArgs += '-'
$prompt | & codex @codexArgs
