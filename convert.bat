@echo off
chcp 65001 > nul
title Конвертер HEX в Z2 + Cardimp

echo ========================================
echo   Конвертер HEX в Z2 + Cardimp
echo ========================================
echo.

:: Проверяем наличие Python
python --version > nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не установлен!
    echo.
    pause
    exit /b 1
)

:: Проверяем наличие скрипта
if not exist "magnit.py" (
    echo [ОШИБКА] Файл magnit.py не найден!
    echo.
    pause
    exit /b 1
)

:: Запускаем основной Python скрипт
python magnit.py

if errorlevel 1 (
    echo.
    echo [ОШИБКА] Ошибка при выполнении!
    pause
    exit /b 1
)

echo.
pause