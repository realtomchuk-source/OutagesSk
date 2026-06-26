@echo off
echo ==========================================
echo Running Collector...
echo ==========================================
cd /d "%~dp0"

python collector.py
if errorlevel 1 (
    echo ERROR in collector.py
    pause
    exit /b
)

echo.
echo ==========================================
echo Running Formatter...
echo ==========================================
python formatter.py
if errorlevel 1 (
    echo ERROR in formatter.py
    pause
    exit /b
)

echo.
echo ==========================================
echo Committing to Git...
echo ==========================================
git add data/
git commit -m "Manual local update"

echo.
echo ==========================================
echo Pushing to GitHub...
echo ==========================================
git push
if errorlevel 1 (
    echo ERROR pushing to GitHub.
    pause
    exit /b
)

echo ==========================================
echo SUCCESS!
echo Please refresh the admin panel with Ctrl+F5
echo ==========================================
pause
