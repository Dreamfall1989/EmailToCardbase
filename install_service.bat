@echo off
chcp 65001 >nul
title Установка службы обработки почты

:: Получаем путь к папке, где лежит этот bat-файл
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo ============================================
echo УСТАНОВКА СЛУЖБЫ ОБРАБОТКИ ПОЧТЫ
echo ============================================
echo.
echo Папка установки: %SCRIPT_DIR%
echo.

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ОШИБКА] Запустите от имени Администратора!
    pause
    exit /b 1
)

python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ОШИБКА] Python не найден!
    pause
    exit /b 1
)

echo Проверка библиотек...
python -c "import win32serviceutil" >nul 2>&1
if %errorLevel% neq 0 (
    echo Установка pywin32...
    python -m pip install pywin32
)

:: Создаём папки
mkdir "%SCRIPT_DIR%logs" 2>nul
mkdir "%SCRIPT_DIR%attachments" 2>nul
mkdir "%SCRIPT_DIR%OLD" 2>nul

:: Проверяем config.ini
if not exist "%SCRIPT_DIR%config.ini" (
    echo.
    echo [ВНИМАНИЕ] Файл config.ini не найден.
    echo Он будет создан автоматически с настройками по умолчанию.
    echo Не забудьте указать пароль приложения в config.ini!
    echo.
    pause
)

:: Устанавливаем службу
echo Установка службы...
python "%SCRIPT_DIR%email_service.py" install
if %errorLevel% neq 0 (
    echo [ОШИБКА] Не удалось установить службу!
    pause
    exit /b 1
)

python "%SCRIPT_DIR%email_service.py" start
if %errorLevel% neq 0 (
    echo [ОШИБКА] Не удалось запустить службу!
    pause
    exit /b 1
)

echo.
echo ============================================
echo СЛУЖБА УСТАНОВЛЕНА И ЗАПУЩЕНА!
echo ============================================
echo.
echo Управление службой:
echo   Запуск:   python "%SCRIPT_DIR%email_service.py" start
echo   Остановка: python "%SCRIPT_DIR%email_service.py" stop
echo   Удаление: "%SCRIPT_DIR%uninstall_service.bat"
echo.
echo Логи: %SCRIPT_DIR%logs\email_service.log
echo Конфиг: %SCRIPT_DIR%config.ini
echo.
pause