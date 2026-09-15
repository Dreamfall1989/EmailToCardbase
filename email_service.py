"""
Служба Windows для автоматической обработки почты и скриптов
"""
import os
import sys
import time
import shutil
import glob
import subprocess
import logging
import logging.handlers
from datetime import datetime
import socket
import configparser
import threading


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

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

def get_python_exe():
    if 'pythonservice' in sys.executable.lower():
        python_dir = os.path.dirname(sys.executable)
        possible = os.path.join(python_dir, 'python.exe')
        if os.path.exists(possible):
            return possible
        for path in os.environ.get('PATH', '').split(';'):
            possible = os.path.join(path.strip(), 'python.exe')
            if os.path.exists(possible):
                return possible
    return sys.executable

def load_config():
    config = configparser.ConfigParser()
    
    defaults = {
        'check_interval_minutes': 60,
        'email': '', 'password': '',
        'from_filter': '', 'subject_filter': '', 'days_back': 0,
        'attachments_folder': 'attachments', 'logs_folder': 'logs',
        'delete_processed': False, 'mark_as_read': True,
        'scripts': 'mail, chg, magnit',
    }
    
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE, encoding='utf-8')
        scripts_str = config.get('tasks', 'scripts', fallback='mail, chg, magnit')
        scripts = [s.strip() for s in scripts_str.split(',') if s.strip()]
        
        return {
            'check_interval_minutes': config.getint('schedule', 'check_interval_minutes', fallback=60),
            'email': config.get('email', 'email', fallback=''),
            'password': config.get('email', 'password', fallback=''),
            'from_filter': config.get('filter', 'from_filter', fallback=''),
            'subject_filter': config.get('filter', 'subject_filter', fallback=''),
            'days_back': config.getint('filter', 'days_back', fallback=0),
            'attachments_folder': config.get('paths', 'attachments_folder', fallback='attachments'),
            'logs_folder': config.get('paths', 'logs_folder', fallback='logs'),
            'delete_processed': config.getboolean('options', 'delete_processed', fallback=False),
            'mark_as_read': config.getboolean('options', 'mark_as_read', fallback=True),
            'scripts': scripts,
        }
    return defaults

def setup_logging(logs_folder):
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
        self.python_exe = get_python_exe()
        
        self.attachments_dir = os.path.join(SCRIPT_DIR, self.config['attachments_folder'])
        os.makedirs(self.attachments_dir, exist_ok=True)
        
        self.logger.info("=" * 60)
        self.logger.info("СЛУЖБА ИНИЦИАЛИЗИРОВАНА")
        self.logger.info(f"Папка: {SCRIPT_DIR}")
        self.logger.info(f"Python: {self.python_exe}")
        self.logger.info(f"Интервал: {self.config['check_interval_minutes']} мин")
        self.logger.info(f"Задачи: {', '.join(self.config['scripts'])}")
        self.logger.info("=" * 60)
        self.logger.handlers[0].flush()
    
    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.logger.info("Служба останавливается...")
        self.logger.handlers[0].flush()
        win32event.SetEvent(self.stop_event)
        self.is_running = False
    
    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.logger.info("СЛУЖБА ЗАПУЩЕНА")
        self.logger.handlers[0].flush()
        
        thread = threading.Thread(target=self._run_loop, daemon=True)
        thread.start()
        
        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
        self.logger.info("Служба остановлена")
        self.logger.handlers[0].flush()
    
    def _run_loop(self):
        try:
            self.logger.info(">>> Старт первого цикла...")
            self.logger.handlers[0].flush()
            self.process_emails()
            self.logger.info(">>> Первый цикл завершён")
            self.logger.handlers[0].flush()
        except Exception as e:
            self.logger.error(f"Ошибка в первом цикле: {e}")
            self.logger.handlers[0].flush()
            return
        
        interval = self.config['check_interval_minutes'] * 60
        
        while self.is_running:
            for _ in range(interval):
                if not self.is_running:
                    return
                time.sleep(1)
            
            if self.is_running:
                self.config = load_config()
                try:
                    self.process_emails()
                except Exception as e:
                    self.logger.error(f"Ошибка в цикле: {e}")
                    self.logger.handlers[0].flush()
    
    def process_emails(self):
        """Основной цикл — запускает скрипты из конфига"""
        self.logger.info("-" * 40)
        self.logger.info(">>> Цикл обработки...")
        self.logger.handlers[0].flush()
        
        scripts = self.config.get('scripts', ['mail', 'chg', 'magnit'])
        
        for script_name in scripts:
            configured_name = script_name
            script_base_name = os.path.splitext(script_name)[0].casefold()

            # magnit.py запускаем только если есть ZIP-файлы
            if script_base_name == 'magnit':
                attachment_zip_files = glob.glob(os.path.join(self.attachments_dir, "*.zip"))
                root_zip_files = glob.glob(os.path.join(SCRIPT_DIR, "*.zip"))

                if not attachment_zip_files and not root_zip_files:
                    self.logger.info(
                        f"{configured_name} пропущен (ZIP-файлы не найдены в "
                        f"{self.attachments_dir} или {SCRIPT_DIR})"
                    )
                    continue
                
                # Перемещаем ZIP в корень перед запуском magnit.py
                for zip_path in attachment_zip_files:
                    try:
                        filename = os.path.basename(zip_path)
                        dest = os.path.join(SCRIPT_DIR, filename)
                        if os.path.exists(dest):
                            name, ext = os.path.splitext(filename)
                            dest = os.path.join(SCRIPT_DIR, f"{name}_{int(time.time())}{ext}")
                        shutil.move(zip_path, dest)
                        self.logger.info(f"  ZIP перемещён: {os.path.basename(dest)}")
                    except Exception as e:
                        self.logger.error(f"  Ошибка перемещения ZIP: {e}")
            
            # Запускаем скрипт (добавляем .py если нужно)
            if not script_name.lower().endswith('.py'):
                script_name = script_name + '.py'
            
            self.run_script(script_name)
        
        self.logger.info(">>> Цикл завершён")
        self.logger.handlers[0].flush()
    
    def run_script(self, script_name):
        """Запуск скрипта отдельным процессом Python"""
        script_path = self.find_script_path(script_name)
        if script_path is None:
            requested_path = os.path.join(SCRIPT_DIR, script_name)
            self.logger.warning(f"Скрипт не найден: {requested_path}")
            return

        command = [self.python_exe, script_path]
        self.logger.info(f"Запуск {script_name} отдельным процессом")
        self.logger.info(f"  Python: {self.python_exe}")
        self.logger.info(f"  Рабочая папка: {SCRIPT_DIR}")
        self.logger.info(f"  Команда: {' '.join(command)}")
        self.logger.handlers[0].flush()

        try:
            result = subprocess.run(
                command,
                cwd=SCRIPT_DIR,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
        except Exception as e:
            self.logger.error(f"Ошибка запуска {script_name}: {type(e).__name__}: {e}")
            self.logger.handlers[0].flush()
            return

        # Логируем stdout
        if result.stdout:
            for line in result.stdout.splitlines():
                if line.strip():
                    self.logger.info(f"  {line.strip()}")

        # Логируем stderr
        if result.stderr:
            for line in result.stderr.splitlines():
                if line.strip():
                    self.logger.error(f"  [ERR] {line.strip()}")

        # Итог
        self.logger.info(f"{script_name}: код возврата {result.returncode}")
        if result.returncode != 0:
            self.logger.error(f"{script_name} завершился с ошибкой")
        else:
            self.logger.info(f"{script_name} выполнен успешно")

        self.logger.handlers[0].flush()

    @staticmethod
    def find_script_path(script_name):
        """Находит Python-скрипт в папке службы без учета регистра имени."""
        requested_name = script_name.casefold()
        for filename in os.listdir(SCRIPT_DIR):
            if filename.casefold() == requested_name:
                return os.path.join(SCRIPT_DIR, filename)
        return None
    
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