import os
import shutil
import subprocess
import time
from datetime import datetime

# ============================================================
# НАСТРОЙКИ
# ============================================================

SOURCE_DIRECTORY = r"D:\FTProot\Chernogolovka\CARDS"
OUTPUT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
ARCHIVE_FOLDER = "CHG_OLD"

CARDIMP_EXECUTABLE = "Cardimp.exe"
CARDIMP_LOGIN = "Admin"
CARDIMP_PASSWORD = "911"
CARDIMP_ALT_PATHS = [
    r"D:\UCS\PDS_ALFA\Cardimp.exe",
]

WAIT_BEFORE_ARCHIVE = 5
SUFFIX_TO_ADD = ",,,,Черноголовка"
FILE_ENCODING = "ansi"

# ============================================================
# ОСНОВНОЙ КОД
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "logs", "CHG_IMP_LOG.txt")

def log_message(message):
    """Простое логирование в файл"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(f"[{timestamp}] {message}\n")
    except:
        pass

def find_txt_file(directory):
    """Поиск любого txt файла в указанной директории"""
    try:
        if not os.path.exists(directory):
            return None
        
        for file in os.listdir(directory):
            if file.lower().endswith('.txt'):
                return os.path.join(directory, file)
        return None
    except:
        return None

def process_and_save_file(source_file, add_suffix=True):
    """Обработка и сохранение файла"""
    with open(source_file, 'r', encoding=FILE_ENCODING) as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    
    if not lines:
        return None, None, None
    
    # Обрабатываем строки если нужно добавить суффикс
    if add_suffix:
        processed_lines = [line + SUFFIX_TO_ADD for line in lines]
        log_message("Суффикс добавлен ко всем строкам")
    else:
        processed_lines = lines
        log_message("Суффиксы уже присутствуют, строки не изменены")
    
    # Сохраняем результат в OUTPUT_DIRECTORY
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"EE_Cards_{timestamp}.txt"
    output_file = os.path.join(OUTPUT_DIRECTORY, output_filename)
    
    # Создаем директорию если её нет
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)
    
    with open(output_file, 'w', encoding=FILE_ENCODING) as f:
        f.write('\n'.join(processed_lines))
    
    log_message(f"Файл сохранен: {output_file}")
    return output_file, timestamp, output_filename

def main():
    """Основная функция"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    log_message("Начало работы")
    log_message(f"Директория скрипта: {script_dir}")
    log_message(f"Директория вывода: {OUTPUT_DIRECTORY}")
    
    # Ищем любой txt файл в исходной директории
    source_file = find_txt_file(SOURCE_DIRECTORY)
    
    if not source_file:
        log_message(f"TXT файлы не найдены в: {SOURCE_DIRECTORY}")
        return
    
    log_message(f"Найден файл: {source_file}")
    
    try:
        # Проверяем, есть ли уже суффикс в строках
        with open(source_file, 'r', encoding=FILE_ENCODING) as f:
            first_line = f.readline().strip()
        
        need_add_suffix = not first_line.endswith(SUFFIX_TO_ADD)
        
        if need_add_suffix:
            log_message("Суффикс отсутствует, будет добавлен")
        else:
            log_message("Суффикс уже присутствует, добавление пропущено")
        
        # Обрабатываем и сохраняем файл
        output_file, timestamp, output_filename = process_and_save_file(source_file, need_add_suffix)
        
        if not output_file:
            os.remove(source_file)
            log_message("Файл пустой, удален")
            return
        
        # Проверяем что файл существует
        if not os.path.exists(output_file):
            log_message(f"ОШИБКА: Файл не создан: {output_file}")
            return
        
        log_message(f"Файл создан: {output_file}")
        log_message(f"Размер: {os.path.getsize(output_file)} байт")
        
        # Удаляем исходный файл
        os.remove(source_file)
        log_message(f"Исходный файл удален: {source_file}")
        
        # Поиск Cardimp
        cardimp_path = None
        if os.path.exists(CARDIMP_EXECUTABLE):
            cardimp_path = os.path.abspath(CARDIMP_EXECUTABLE)
        else:
            for path in CARDIMP_ALT_PATHS:
                if os.path.exists(path):
                    cardimp_path = path
                    break
        
        if cardimp_path:
            try:
                # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: запуск через список аргументов как в рабочем скрипте
                cmd = [cardimp_path, CARDIMP_LOGIN, CARDIMP_PASSWORD, output_file]
                log_message(f"Запуск Cardimp: {' '.join(cmd)}")
                
                # Запускаем Cardimp и ждем завершения
                result = subprocess.run(cmd, capture_output=True, text=True, encoding='cp1251')
                
                if result.returncode == 0:
                    log_message("Cardimp выполнен успешно!")
                else:
                    log_message(f"Cardimp завершился с ошибкой (код: {result.returncode})")
                    if result.stderr:
                        log_message(f"Ошибка: {result.stderr}")
                
            except Exception as e:
                log_message(f"Ошибка запуска Cardimp: {e}")
        else:
            log_message("Cardimp.exe не найден")
        
        # Ждем перед архивацией
        log_message(f"Ожидание {WAIT_BEFORE_ARCHIVE} секунд...")
        time.sleep(WAIT_BEFORE_ARCHIVE)
        
        # Архивация - перемещаем файл из OUTPUT_DIRECTORY в архив
        archive_dir = os.path.join(OUTPUT_DIRECTORY, ARCHIVE_FOLDER)
        os.makedirs(archive_dir, exist_ok=True)
        
        # Перемещаем созданный файл в архив
        if os.path.exists(output_file):
            archive_name = f"{timestamp}_{output_filename}"
            archive_path = os.path.join(archive_dir, archive_name)
            try:
                shutil.move(output_file, archive_path)
                log_message(f"Файл перемещён в архив: {archive_name}")
            except Exception as e:
                log_message(f"Ошибка архивации: {e}")
        
        log_message("Работа завершена успешно")
        
    except Exception as e:
        log_message(f"ОШИБКА: {e}")

if __name__ == "__main__":
    main()