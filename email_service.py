"""
Служба Windows для автоматической обработки почты
Установка: python email_service.py install
Запуск:    python email_service.py start
Удаление:  python email_service.py remove
"""
import os
import sys
import time
import json
import subprocess
import logging
import logging.handlers
from datetime import datetime, timedelta
import shutil
import glob
import socket
import configparser
import threading

# Проверяем pywin32
try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
except ImportError:
    print("Установи pywin32: pip install pywin32")
    sys.exit(1)

# ===== НАСТРОЙКИ =====
SERVICE_NAME = "EmailProcessorService"
SERVICE_DISPLAY_NAME = "Email Attachment Processor"
SERVICE_DESCRIPTION = "Автоматически проверяет почту, скачивает вложения и обрабатывает их"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.ini")
PROCESSED_FILE = os.path.join(SCRIPT_DIR, "processed_emails.json")

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

def get_python_exe():
    """Возвращает путь к python.exe"""
    # Если запущены как служба через pythonservice.exe
    if 'pythonservice' in sys.executable.lower():
        python_dir = os.path.dirname(sys.executable)
        possible = os.path.join(python_dir, 'python.exe')
        if os.path.exists(possible):
            return possible
        # Ищем python в PATH
        for path in os.environ.get('PATH', '').split(';'):
            possible = os.path.join(path.strip(), 'python.exe')
            if os.path.exists(possible):
                return possible
    return sys.executable

def load_config():
    """Загружает настройки из config.ini"""
    config = configparser.ConfigParser()
    
    defaults = {
        'check_interval_minutes': 60, 'first_run_time': '0', 'run_at_time': '',
        'email': 'dreamfall1989@gmail.com', 'password': '',
        'from_filter': '', 'subject_filter': '', 'days_back': 1,
        'attachments_folder': 'attachments', 'logs_folder': 'logs',
        'delete_processed': False, 'mark_as_read': True,
    }
    
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE, encoding='utf-8')
        return {
            'check_interval_minutes': config.getint('schedule', 'check_interval_minutes', fallback=60),
            'first_run_time': config.get('schedule', 'first_run_time', fallback='0'),
            'run_at_time': config.get('schedule', 'run_at_time', fallback=''),
            'email': config.get('email', 'email', fallback=''),
            'password': config.get('email', 'password', fallback=''),
            'from_filter': config.get('filter', 'from_filter', fallback=''),
            'subject_filter': config.get('filter', 'subject_filter', fallback=''),
            'days_back': config.getint('filter', 'days_back', fallback=1),
            'attachments_folder': config.get('paths', 'attachments_folder', fallback='attachments'),
            'logs_folder': config.get('paths', 'logs_folder', fallback='logs'),
            'delete_processed': config.getboolean('options', 'delete_processed', fallback=False),
            'mark_as_read': config.getboolean('options', 'mark_as_read', fallback=True),
        }
    return defaults

def setup_logging(logs_folder):
    """Настраивает логирование"""
    log_dir = os.path.join(SCRIPT_DIR, logs_folder)
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "email_service.log")
    
    logger = logging.getLogger("EmailService")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    
    handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=10, encoding='utf-8'
    )
    handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(handler)
    return logger

# ===== КЛАСС СЛУЖБЫ =====

class EmailProcessorService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY_NAME
    _svc_description_ = SERVICE_DESCRIPTION
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.is_running = True
        self.config = load_config()
        self.logger = setup_logging(self.config['logs_folder'])
        self.last_run_time = None
        self.python_exe = get_python_exe()
        
        self.attachments_dir = os.path.join(SCRIPT_DIR, self.config['attachments_folder'])
        os.makedirs(self.attachments_dir, exist_ok=True)
        
        self.logger.info("=" * 60)
        self.logger.info("СЛУЖБА ИНИЦИАЛИЗИРОВАНА")
        self.logger.info(f"Папка: {SCRIPT_DIR}")
        self.logger.info(f"Python: {self.python_exe}")
        self.logger.info(f"Интервал: {self.config['check_interval_minutes']} мин")
        self.logger.info(f"Отправитель: {self.config['from_filter'] or 'все'}")
        self.logger.info(f"Аккаунт: {self.config['email']}")
        self.logger.info("=" * 60)
    
    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.logger.info("Служба останавливается...")
        win32event.SetEvent(self.stop_event)
        self.is_running = False
    
    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.logger.info("СЛУЖБА ЗАПУЩЕНА")
        
        if not self.config['password']:
            self.logger.error("Пароль не настроен в config.ini!")
        
        # Запускаем цикл в отдельном потоке
        thread = threading.Thread(target=self._run_loop, daemon=True)
        thread.start()
        
        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
        self.logger.info("Служба остановлена")
    
    def _run_loop(self):
        # Первый запуск
        self.logger.info("Первый запуск: немедленно")
        self.process_emails()
        
        interval = self.config['check_interval_minutes'] * 60
        
        while self.is_running:
            # Ждём интервал, проверяя каждую секунду флаг остановки
            for _ in range(interval):
                if not self.is_running:
                    return
                time.sleep(1)
            
            if self.is_running:
                self.process_emails()
    
    def process_emails(self):
        self.logger.info("-" * 40)
        self.logger.info(">>> Цикл проверки почты...")
        self.last_run_time = datetime.now()
        
        if not self.check_internet():
            self.logger.warning("Нет интернета. Пропускаем.")
            return
        
        # 1. mail.py
        if not self.run_script("mail.py"):
            return
        
        # 2. Проверяем ZIP
        zip_files = glob.glob(os.path.join(self.attachments_dir, "*.zip"))
        
        if not zip_files:
            self.logger.info("Нет новых ZIP-файлов")
            return
        
        self.logger.info(f"Найдено ZIP: {len(zip_files)}")
        
        # 3. Перемещаем в корень
        for zip_path in zip_files:
            try:
                filename = os.path.basename(zip_path)
                dest = os.path.join(SCRIPT_DIR, filename)
                if os.path.exists(dest):
                    name, ext = os.path.splitext(filename)
                    dest = os.path.join(SCRIPT_DIR, f"{name}_{int(time.time())}{ext}")
                shutil.move(zip_path, dest)
                self.logger.info(f"  ZIP перемещён: {os.path.basename(dest)}")
            except Exception as e:
                self.logger.error(f"  Ошибка перемещения: {e}")
        
        # 4. main.py
        self.logger.info("Запуск обработки...")
        self.run_script("main.py")
    
    def run_script(self, script_name):
        script_path = os.path.join(SCRIPT_DIR, script_name)
        if not os.path.exists(script_path):
            self.logger.error(f"Скрипт не найден: {script_path}")
            return False
        
        try:
            self.logger.info(f"Запуск {script_name}...")
            result = subprocess.run(
                [self.python_exe, script_path],
                capture_output=True, text=True,
                encoding='utf-8', errors='ignore',
                cwd=SCRIPT_DIR, timeout=300
            )
            
            if result.stdout:
                for line in result.stdout.split('\n'):
                    if line.strip():
                        self.logger.info(f"  {line.strip()}")
            
            if result.stderr:
                for line in result.stderr.split('\n'):
                    if line.strip():
                        self.logger.error(f"  [ERR] {line.strip()}")
            
            if result.returncode == 0:
                self.logger.info(f"{script_name} выполнен успешно")
                return True
            else:
                self.logger.error(f"{script_name}: код ошибки {result.returncode}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"Таймаут {script_name}")
            return False
        except Exception as e:
            self.logger.error(f"Ошибка {script_name}: {e}")
            return False
    
    def check_internet(self):
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            return False

if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(EmailProcessorService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(EmailProcessorService)