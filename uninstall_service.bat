@echo off
chcp 65001 >nul
title Удаление службы обработки почты

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo ============================================
echo УДАЛЕНИЕ СЛУЖБЫ ОБРАБОТКИ ПОЧТЫ
echo ============================================
echo.

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ОШИБКА] Запустите от имени Администратора!
    pause
    exit /b 1
)

echo Остановка службы...
python "%SCRIPT_DIR%email_service.py" stop 2>nul

echo Удаление службы...
python "%SCRIPT_DIR%email_service.py" remove

echo.
echo СЛУЖБА УДАЛЕНА!
pause