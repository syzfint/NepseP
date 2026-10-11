# One-click PowerShell GitHub Sync for SYZ-FINT
param(
    [string]$Message = ""
)

if ($Message -eq "") {
    python scripts/git_sync.py
} else {
    python scripts/git_sync.py "$Message"
}
