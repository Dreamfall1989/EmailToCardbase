import io
import sys

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import os
import shutil
import zipfile
import subprocess
import time
from datetime import datetime
import glob

# ===== НАСТРОЙКА ЛОГИРОВАНИЯ =====
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "magnit_card_import.txt")

def log_message(msg):
    """Вывод сообщения с временем в консоль и в лог-файл"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass

def find_zip_file():
    """Поиск ZIP файла с именем Attachments_svc_sigur_mail_magnit.ru_*.zip"""
    log_message("Поиск ZIP архива...")
    
    all_zips = glob.glob("*.zip")
    
    pattern_zips = glob.glob("Attachments_svc_sigur_mail_magnit.ru_*.zip")
    if pattern_zips:
        return pattern_zips[0]
    
    for f in all_zips:
        if f.startswith("Attachments_svc_sigur_mail_magnit.ru_"):
            return f
    
    if all_zips:
        log_message(f"Найден ZIP: {all_zips[0]}")
        return all_zips[0]
    
    return None

def extract_zip_with_python(zip_path, extract_to):
    """Распаковка ZIP архива с помощью Python"""
    try:
        log_message(f"Распаковка {os.path.basename(zip_path)}...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        return True
    except Exception as e:
        log_message(f"Ошибка распаковки: {e}")
        return False

def find_csv_file(root_folder):
    """Поиск CSV файла рекурсивно"""
    log_message("Поиск CSV файла...")
    
    for root, dirs, files in os.walk(root_folder):
        for file in files:
            if file.lower().endswith('.csv'):
                file_path = os.path.join(root, file)
                log_message(f"Найден CSV напрямую: {file}")
                return file_path
        
        for file in files:
            if file.lower().endswith('.zip'):
                zip_path = os.path.join(root, file)
                log_message(f"Проверка архива: {file}")
                
                try:
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        for member in zip_ref.namelist():
                            if member.lower().endswith('.csv'):
                                log_message(f"Найден CSV внутри архива: {member}")
                                
                                extract_folder = os.path.join(root, 'temp_csv')
                                os.makedirs(extract_folder, exist_ok=True)
                                zip_ref.extract(member, extract_folder)
                                
                                csv_path = os.path.join(extract_folder, member)
                                if os.path.exists(csv_path):
                                    return csv_path
                                
                                for f in os.listdir(extract_folder):
                                    if f.lower().endswith('.csv'):
                                        return os.path.join(extract_folder, f)
                except Exception as e:
                    log_message(f"Ошибка чтения архива {file}: {e}")
    
    return None

def copy_csv_to_root(csv_path, root_folder):
    """Копирует CSV в корневую папку и возвращает новое имя"""
    if not csv_path:
        return None
    
    filename = os.path.basename(csv_path)
    dest_path = os.path.join(root_folder, filename)
    
    try:
        shutil.copy2(csv_path, dest_path)
        log_message(f"CSV скопирован: {filename}")
        return filename
    except Exception as e:
        log_message(f"Ошибка копирования CSV: {e}")
        return None

def run_converter():
    """Запускает скрипт конвертации"""
    log_message("Запуск конвертации...")
    converter_path = os.path.join(SCRIPT_DIR, "convert_last12.py")
    command = [sys.executable, converter_path]
    log_message(f"Python: {sys.executable}")
    log_message(f"Рабочая папка: {os.getcwd()}")
    log_message(f"Команда: {' '.join(command)}")
    
    try:
        result = subprocess.run(
            command,
            cwd=SCRIPT_DIR,
            capture_output=True,
            text=True,
            encoding='cp1251',
            errors='replace'
        )

        if result.stdout:
            for line in result.stdout.splitlines():
                if line.strip():
                    log_message(f"  stdout: {line}")
        if result.stderr:
            for line in result.stderr.splitlines():
                if line.strip():
                    log_message(f"  stderr: {line}")
        log_message(f"Код возврата конвертера: {result.returncode}")
        
        if result.returncode == 0:
            log_message("Конвертация выполнена успешно")
            return True
        else:
            log_message("Ошибка конвертации")
            return False
    except Exception as e:
        log_message(f"Ошибка запуска конвертации: {e}")
        return False

def run_cardimp(cardimp_path, login, password, txt_file):
    """Запускает Cardimp"""
    log_message("Запуск Cardimp...")
    cmd = [cardimp_path, login, password, txt_file]
    log_message(f"Команда: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='cp1251')
        
        if result.returncode == 0:
            log_message("Cardimp выполнен успешно!")
            return True
        else:
            log_message(f"Cardimp завершился с ошибкой (код: {result.returncode})")
            if result.stderr:
                log_message(f"Ошибка: {result.stderr}")
            return False
    except Exception as e:
        log_message(f"Ошибка запуска Cardimp: {e}")
        return False

def log_processing_error(message, zip_archive):
    """Фиксирует ошибку и оставляет архив для визуальной проверки"""
    log_message(message)
    log_message(f"ZIP оставлен для проверки: {os.path.abspath(zip_archive)}")

def move_files_to_old(files_to_move, old_folder):
    """Перемещает файлы в папку OLD, переименовывая при совпадении имён"""
    log_message(f"Перемещение файлов в {old_folder}...")
    
    for file_path in files_to_move:
        if file_path and os.path.exists(file_path):
            try:
                filename = os.path.basename(file_path)
                dest_path = os.path.join(old_folder, filename)
                
                if os.path.exists(dest_path):
                    name, ext = os.path.splitext(filename)
                    counter = 1
                    while os.path.exists(dest_path):
                        new_name = f"{name}_{counter}{ext}"
                        dest_path = os.path.join(old_folder, new_name)
                        counter += 1
                    log_message(f"  Файл уже существует, переименован: {os.path.basename(dest_path)}")
                
                shutil.move(file_path, dest_path)
                log_message(f"  Перемещен: {os.path.basename(dest_path)}")
                
            except Exception as e:
                log_message(f"  Ошибка перемещения {os.path.basename(file_path)}: {e}")

def cleanup_old_csvs(directory):
    """Удаляет одиночные CSV файлы в корне (не во временных папках)"""
    for f in os.listdir(directory):
        if f.lower().endswith('.csv') and not f.startswith('~'):
            filepath = os.path.join(directory, f)
            if os.path.isfile(filepath) and 'temp_extract' not in filepath:
                try:
                    os.remove(filepath)
                    log_message(f"Удалён старый CSV: {f}")
                except Exception as e:
                    log_message(f"Не удалось удалить {f}: {e}")

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    cardimp_path = "Cardimp.exe"
    login = "Admin"
    password = "911"
    old_folder = "OLD"
    wait_time = 5

    attachments_dir = os.path.join(script_dir, "attachments")
    if os.path.exists(attachments_dir):
        for f in os.listdir(attachments_dir):
            if f.lower().endswith('.zip'):
                src = os.path.join(attachments_dir, f)
                dst = os.path.join(script_dir, f)
                if not os.path.exists(dst):
                    shutil.move(src, dst)
                    log_message(f"ZIP перемещён из attachments: {f}")
    
    if not os.path.exists(cardimp_path):
        alt_paths = [r"D:\UCS\PDS_ALFA\Cardimp.exe"]
        for path in alt_paths:
            if os.path.exists(path):
                cardimp_path = path
                log_message(f"Найден Cardimp: {cardimp_path}")
                break
        use_cardimp = os.path.exists(cardimp_path)
    else:
        use_cardimp = True
    
    if use_cardimp:
        log_message(f"Cardimp найден: {cardimp_path}")
    else:
        log_message("ПРЕДУПРЕЖДЕНИЕ: Cardimp.exe не найден!")
    
    log_message("=" * 50)
    log_message("Начало работы")
    
    os.makedirs(old_folder, exist_ok=True)
    
    zip_archive = find_zip_file()
    if not zip_archive:
        all_zips = glob.glob("*.zip")
        if all_zips:
            zip_archive = all_zips[0]
            log_message(f"Найден архив: {zip_archive}")
        else:
            log_message("ZIP файлы не найдены — нечего обрабатывать")
            cleanup_old_csvs(script_dir)
            return
    
    log_message(f"Выбран архив: {zip_archive}")
    
    temp_folder = "temp_extract"
    if os.path.exists(temp_folder):
        shutil.rmtree(temp_folder)
    os.makedirs(temp_folder, exist_ok=True)
    
    if not extract_zip_with_python(zip_archive, temp_folder):
        log_processing_error("ОШИБКА: Не удалось распаковать архив!", zip_archive)
        sys.exit(1)
    
    csv_path = find_csv_file(temp_folder)
    if not csv_path:
        log_processing_error("ОШИБКА: CSV файл не найден!", zip_archive)
        sys.exit(1)
    
    csv_filename = copy_csv_to_root(csv_path, '.')
    if not csv_filename:
        log_processing_error("ОШИБКА: Не удалось скопировать CSV файл!", zip_archive)
        sys.exit(1)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_csv_name = f"{timestamp}.csv"
    txt_file = f"{timestamp}.txt"
    
    if os.path.exists(csv_filename):
        os.rename(csv_filename, new_csv_name)
        log_message(f"CSV переименован: {new_csv_name}")
    
    if not run_converter():
        log_processing_error("ОШИБКА: Конвертация не выполнена!", zip_archive)
        sys.exit(1)
    
    if not os.path.exists(txt_file):
        log_processing_error(f"ОШИБКА: TXT файл не создан: {txt_file}", zip_archive)
        sys.exit(1)
    
    log_message(f"TXT файл создан: {txt_file}")
    
    if use_cardimp:
        if not run_cardimp(cardimp_path, login, password, txt_file):
            log_processing_error("ОШИБКА: Cardimp не обработал TXT файл!", zip_archive)
            sys.exit(1)
    
    log_message(f"Ожидание {wait_time} секунд...")
    time.sleep(wait_time)
    
    files_to_move = [new_csv_name, txt_file, zip_archive]
    for f in os.listdir('.'):
        if f.endswith('.zip') and f not in files_to_move:
            files_to_move.append(f)
    
    move_files_to_old(files_to_move, old_folder)
    
    if os.path.exists(temp_folder):
        shutil.rmtree(temp_folder)
        log_message("Временная папка удалена")
    
    cleanup_old_csvs(script_dir)
    
    log_message("=" * 50)
    log_message("Работа завершена!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log_message("Прервано пользователем")
    except Exception as e:
        log_message(f"Непредвиденная ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)