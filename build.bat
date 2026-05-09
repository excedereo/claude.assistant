@echo off
echo Building claude.assistant.exe ...

.venv\Scripts\python.exe -c "from PIL import Image; img = Image.open('assets/claudeHappy.png').convert('RGBA'); img.save('assets/claude.ico', format='ICO', sizes=[(256,256),(128,128),(64,64),(32,32),(16,16)])"
if errorlevel 1 (
    echo Failed to convert icon. Make sure Pillow is installed.
    pause
    exit /b 1
)

.venv\Scripts\pyinstaller.exe --noconfirm ^
  --onefile ^
  --windowed ^
  --name claude_assistant ^
  --add-data "assets;assets" ^
  --add-data "config.json;." ^
  --icon "assets\claude.ico" ^
  --hidden-import "pystray._win32" ^
  --hidden-import "pystray" ^
  --hidden-import "PIL" ^
  --hidden-import "PIL.Image" ^
  --hidden-import "PIL.ImageTk" ^
  --hidden-import "PIL.ImageDraw" ^
  main.py

echo.
if exist dist\claude_assistant.exe (
    echo Done: dist\claude_assistant.exe
) else (
    echo Build failed.
)
pause
