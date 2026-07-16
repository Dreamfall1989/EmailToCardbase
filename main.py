import sys
import io

# Для Windows
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
import sys

def log_message(msg):
    """Вывод сообщения с временем"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")

def find_zip_file():
    """Поиск ZIP файла с именем Attachments_svc_sigur_mail_magnit.ru_*.zip"""
    log_message("Поиск ZIP архива...")
    
    # Ищем все ZIP файлы
    all_zips = glob.glob("*.zip")
    
    # Сначала ищем точное совпадение паттерна
    pattern_zips = glob.glob("Attachments_svc_sigur_mail_magnit.ru_*.zip")
    if pattern_zips:
        return pattern_zips[0]
    
    # Ищем все ZIP, начинающиеся с Attachments
    for f in all_zips:
        if f.startswith("Attachments_svc_sigur_mail_magnit.ru_"):
            return f
    
    # Если ничего не нашли, берем первый ZIP
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
    
    # Проходим по всем папкам и файлам
    for root, dirs, files in os.walk(root_folder):
        # Сначала ищем CSV напрямую
        for file in files:
            if file.lower().endswith('.csv'):
                file_path = os.path.join(root, file)
                log_message(f"Найден CSV напрямую: {file}")
                return file_path
        
        # Затем ищем CSV внутри ZIP архивов
        for file in files:
            if file.lower().endswith('.zip'):
                zip_path = os.path.join(root, file)
                log_message(f"Проверка архива: {file}")
                
                try:
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        # Ищем CSV внутри ZIP
                        for member in zip_ref.namelist():
                            if member.lower().endswith('.csv'):
                                log_message(f"Найден CSV внутри архива: {member}")
                                
                                # Извлекаем CSV
                                extract_folder = os.path.join(root, 'temp_csv')
                                os.makedirs(extract_folder, exist_ok=True)
                                zip_ref.extract(member, extract_folder)
                                
                                # Получаем полный путь к извлеченному файлу
                                csv_path = os.path.join(extract_folder, member)
                                if os.path.exists(csv_path):
                                    return csv_path
                                
                                # Если файл в подпапке, ищем его
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
    
    # Копируем файл в корень
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
    
    try:
        result = subprocess.run(
            [sys.executable, "convert_last12.py"],
            capture_output=True,
            text=True,
            encoding='cp1251'  # Используем кодировку Windows
        )
        
        if result.returncode == 0:
            log_message("Конвертация выполнена успешно")
            return True
        else:
            log_message(f"Ошибка конвертации: {result.stderr}")
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

def move_files_to_old(files_to_move, old_folder):
    """Перемещает файлы в папку OLD, переименовывая при совпадении имён"""
    log_message(f"Перемещение файлов в {old_folder}...")
    
    for file_path in files_to_move:
        if file_path and os.path.exists(file_path):
            try:
                filename = os.path.basename(file_path)
                dest_path = os.path.join(old_folder, filename)
                
                # Если файл с таким именем уже есть в OLD — добавляем суффикс
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

def main():
    # Параметры
    cardimp_path = "Cardimp.exe"
    login = "Admin"
    password = "911"
    old_folder = "OLD"
    wait_time = 5  # 5 сек

    # ===== НОВОЕ: Проверяем папку attachments =====
    attachments_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "attachments")
    if os.path.exists(attachments_dir):
        for f in os.listdir(attachments_dir):
            if f.lower().endswith('.zip'):
                src = os.path.join(attachments_dir, f)
                dst = os.path.join('.', f)
                if not os.path.exists(dst):
                    shutil.move(src, dst)
                    log_message(f"ZIP перемещён из attachments: {f}")
    
    # Проверяем Cardimp
    if not os.path.exists(cardimp_path):
        # Проверяем альтернативные пути
        alt_paths = [
            r"D:\UCS\PDS_ALFA\Cardimp.exe",
        ]
        for path in alt_paths:
            if os.path.exists(path):
                cardimp_path = path
                log_message(f"Найден Cardimp: {cardimp_path}")
                break
        
        if not os.path.exists(cardimp_path):
            log_message(f"ПРЕДУПРЕЖДЕНИЕ: Cardimp.exe не найден!")
            log_message("Будет выполнена только конвертация.")
            use_cardimp = False
        else:
            use_cardimp = True
    else:
        use_cardimp = True
        log_message(f"Cardimp найден: {cardimp_path}")
    
    log_message("=" * 50)
    log_message("Начало работы")
    
    # Создаем папку OLD
    os.makedirs(old_folder, exist_ok=True)
    
    # Ищем ZIP архив
    zip_archive = find_zip_file()
    if not zip_archive:
        log_message("ОШИБКА: ZIP архив не найден!")
        log_message("Ищем любой ZIP файл...")
        all_zips = glob.glob("*.zip")
        if all_zips:
            zip_archive = all_zips[0]
            log_message(f"Найден архив: {zip_archive}")
        else:
            log_message("ОШИБКА: ZIP файлы не найдены!")
            sys.exit(1)
    
    log_message(f"Выбран архив: {zip_archive}")
    
    # Создаем временную папку
    temp_folder = "temp_extract"
    if os.path.exists(temp_folder):
        shutil.rmtree(temp_folder)
    os.makedirs(temp_folder, exist_ok=True)
    
    # Распаковываем архив
    if not extract_zip_with_python(zip_archive, temp_folder):
        log_message("ОШИБКА: Не удалось распаковать архив!")
        sys.exit(1)
    
    # Ищем CSV файл
    csv_path = find_csv_file(temp_folder)
    if not csv_path:
        log_message("ОШИБКА: CSV файл не найден!")
        sys.exit(1)
    
    # Копируем CSV в корень
    csv_filename = copy_csv_to_root(csv_path, '.')
    if not csv_filename:
        sys.exit(1)
    
    # Получаем временную метку
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_csv_name = f"{timestamp}.csv"
    txt_file = f"{timestamp}.txt"
    
    # Переименовываем CSV
    if os.path.exists(csv_filename):
        os.rename(csv_filename, new_csv_name)
        log_message(f"CSV переименован: {new_csv_name}")
    
    # Запускаем конвертацию
    if not run_converter():
        sys.exit(1)
    
    # Проверяем созданный TXT
    if not os.path.exists(txt_file):
        log_message(f"ОШИБКА: TXT файл не создан: {txt_file}")
        sys.exit(1)
    
    log_message(f"TXT файл создан: {txt_file}")
    
    # Запускаем Cardimp
    if use_cardimp:
        run_cardimp(cardimp_path, login, password, txt_file)
    
    # Ждем перед перемещением
    log_message(f"Ожидание {wait_time} секунд...")
    time.sleep(wait_time)
    
    # Перемещаем файлы в OLD
    files_to_move = [new_csv_name, txt_file, zip_archive]
    
    # Добавляем все остальные ZIP файлы
    for f in os.listdir('.'):
        if f.endswith('.zip') and f not in files_to_move:
            files_to_move.append(f)
    
    move_files_to_old(files_to_move, old_folder)
    
    # Удаляем временную папку
    if os.path.exists(temp_folder):
        shutil.rmtree(temp_folder)
        log_message("Временная папка удалена")
    
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