@echo off
pip install PyQt6
if %ERRORLEVEL% neq 0 (
    echo Failed to install PyQt6. Try running as Administrator.
    pause
    exit /b %ERRORLEVEL%
)
python stfs_extract_gui.py
pause
