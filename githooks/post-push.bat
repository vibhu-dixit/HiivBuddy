@echo off
echo 🔁 hotfix-context-engine: ingesting commit context into Supermemory...
"C:\Projects\hotfix-context-engine\.venv\Scripts\python.exe" -m ingestion.handler --repo "C:\Projects\HiivBuddy"
if %errorlevel% == 0 (
    echo ✅ hotfix-context-engine: ingestion complete.
) else (
    echo ⚠️  hotfix-context-engine: ingestion failed. Push succeeded.
)
exit 0
