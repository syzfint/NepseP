# Setup Windows Scheduled Task for Daily NEPSE Lakehouse Streamer
# Target: Runs Sunday through Thursday at 10:40 AM Local (10:55 AM NPT)

$PythonExe = "C:\Users\achar\AppData\Local\Programs\Python\Python313\python.exe"
$ScriptPath = "c:\Users\achar\Downloads\neps\scripts\01_etl_and_ingestion\06_live_websocket_lakehouse_streamer.py"
$TaskName = "NEPSE_Daily_Lakehouse_Streamer"

Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "  CONFIGURING NEPSE DAILY LAKEHOUSE STREAMER IN WINDOWS TASK SCHEDULER    " -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan

# Unregister if already exists
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removing existing scheduled task: $TaskName..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Action: Run python streamer script
$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$ScriptPath`"" -WorkingDirectory "c:\Users\achar\Downloads\neps"

# Trigger: Sunday through Thursday at 10:40 AM (10:55 AM NPT)
$DaysOfWeek = @("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday")
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DaysOfWeek -At "10:40AM"

# Settings: Start when available, stop if running more than 5 hours (market ends at 3 PM NPT)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 5)

# Register the task under current user
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Daily NEPSE Socket Lakehouse Streamer (11:00 AM - 3:00 PM NPT)"

Write-Host "`nTask successfully registered: $TaskName" -ForegroundColor Green
Write-Host "Scheduled Days: Sunday, Monday, Tuesday, Wednesday, Thursday" -ForegroundColor Green
Write-Host "Trigger Time:   10:40 AM Local Time (10:55 AM NPT)" -ForegroundColor Green
Write-Host "Target Script:  $ScriptPath" -ForegroundColor Green
