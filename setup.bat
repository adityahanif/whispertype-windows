@echo off
echo ============================================
echo  WhisperType - Setup Installer (Windows)
echo ============================================
echo.

:: Cek Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python tidak ditemukan!
    echo Download Python di: https://python.org/downloads
    echo Pastikan centang "Add Python to PATH" saat install.
    pause
    exit /b 1
)

echo [1/4] Membuat virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

echo [2/4] Upgrade pip...
python -m pip install --upgrade pip --quiet

echo [3/4] Install dependensi...
pip install faster-whisper sounddevice numpy pyperclip pyautogui --quiet

echo [4/4] Selesai!
echo.
echo ============================================
echo  Jalankan aplikasi:
echo    venv\Scripts\activate
echo    python stt_app.py
echo.
echo  Atau klik dua kali: run.bat
echo ============================================
pause
