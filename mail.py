"""
Модифицированный mail.py с защитой от повторного скачивания
"""
import os
import sys
import json
import imaplib
import email
from email.header import decode_header
import re
from datetime import datetime, timedelta
import sys
import io

# Для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ===== ЗАГРУЗКА НАСТРОЕК ИЗ config.ini =====
import configparser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.ini")
PROCESSED_FILE = os.path.join(SCRIPT_DIR, "processed_emails.json")

# Загружаем конфиг
config = configparser.ConfigParser()
if os.path.exists(CONFIG_FILE):
    config.read(CONFIG_FILE, encoding='utf-8')
    EMAIL = config.get('email', 'email', fallback='dreamfall1989@gmail.com')
    PASSWORD = config.get('email', 'password', fallback='')
    FROM_FILTER_STR = config.get('filter', 'from_filter', fallback='')
    FROM_FILTER = [x.strip() for x in FROM_FILTER_STR.split(',') if x.strip()]
    SUBJECT_FILTER_STR = config.get('filter', 'subject_filter', fallback='')
    SUBJECT_FILTER = [x.strip() for x in SUBJECT_FILTER_STR.split(',') if x.strip()]
    DAYS_BACK = config.getint('filter', 'days_back', fallback=1)
    ATTACHMENTS_FOLDER = config.get('paths', 'attachments_folder', fallback='attachments')
    DELETE_PROCESSED = config.getboolean('options', 'delete_processed', fallback=False)
    MARK_AS_READ = config.getboolean('options', 'mark_as_read', fallback=True)
else:
    # Настройки по умолчанию
    EMAIL = "dreamfall1989@gmail.com"
    PASSWORD = ""
    FROM_FILTER = ["sadihova75@gmail.com"]
    SUBJECT_FILTER = []
    DAYS_BACK = 1
    ATTACHMENTS_FOLDER = "attachments"
    DELETE_PROCESSED = False
    MARK_AS_READ = True

DOWNLOAD_FOLDER = os.path.join(SCRIPT_DIR, ATTACHMENTS_FOLDER)
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ===== УПРАВЛЕНИЕ ОБРАБОТАННЫМИ ПИСЬМАМИ =====
def load_processed_emails():
    """Загружает список обработанных писем"""
    if os.path.exists(PROCESSED_FILE):
        try:
            with open(PROCESSED_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def is_email_processed(email_id):
    """Проверяет, было ли письмо уже обработано"""
    processed = load_processed_emails()
    for item in processed:
        if item['id'] == email_id:
            return True
    return False

def mark_email_processed(email_id, subject, date_str):
    """Отмечает письмо как обработанное"""
    processed = load_processed_emails()
    
    # Проверяем, нет ли уже такого ID
    for item in processed:
        if item['id'] == email_id:
            return
    
    processed.append({
        'id': email_id,
        'subject': subject[:100],
        'date': date_str,
        'processed_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    # Храним последние 1000 записей
    if len(processed) > 1000:
        processed = processed[-1000:]
    
    with open(PROCESSED_FILE, 'w', encoding='utf-8') as f:
        json.dump(processed, f, ensure_ascii=False, indent=2)

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
def decode_mime_header(header_value):
    """Декодирует заголовок письма"""
    if header_value is None:
        return ""
    decoded_parts = decode_header(header_value)
    result = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            try:
                result += part.decode(encoding or "utf-8", errors="ignore")
            except:
                result += part.decode("utf-8", errors="ignore")
        else:
            result += str(part)
    return result

def save_attachments(msg, email_subject, email_date):
    """Сохраняет вложения из письма"""
    saved_files = []
    safe_subject = re.sub(r'[<>:"/\\|?*]', '_', email_subject)[:50]
    date_str = email_date.strftime("%Y-%m-%d_%H%M%S") if email_date else "unknown_date"
    
    for part in msg.walk():
        if part.get_content_maintype() == 'multipart':
            continue
        
        content_disposition = part.get("Content-Disposition", "")
        if "attachment" in content_disposition or part.get_filename():
            filename = part.get_filename()
            if filename:
                filename = decode_mime_header(filename)
                unique_name = f"{date_str}_{safe_subject}_{filename}"
                filepath = os.path.join(DOWNLOAD_FOLDER, unique_name)
                
                with open(filepath, "wb") as f:
                    f.write(part.get_payload(decode=True))
                
                saved_files.append(filepath)
                print(f"  [OK] Сохранено: {filepath}")
    
    return saved_files

# ===== ОСНОВНАЯ ЛОГИКА =====
def main():
    print("=" * 60)
    print(">>> ПРОВЕРКА ПОЧТЫ...")
    print("=" * 60)
    
    if not PASSWORD:
        print("[ERROR] Пароль не настроен в config.ini!")
        sys.exit(1)
    
    try:
        # Подключаемся
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL, PASSWORD)
        print("[OK] Подключение выполнено\n")
        
        mail.select("inbox")
        
 # Формируем поисковый запрос
        search_criteria = []
        
        if FROM_FILTER:
            if len(FROM_FILTER) == 1:
                search_criteria.append(f'FROM "{FROM_FILTER[0].strip()}"')
            elif len(FROM_FILTER) == 2:
                # Правильный синтаксис: OR FROM "a" FROM "b"
                search_criteria.append(f'OR FROM "{FROM_FILTER[0].strip()}" FROM "{FROM_FILTER[1].strip()}"')
            else:
                # Больше двух: OR (OR FROM "a" FROM "b") FROM "c"
                parts = [f'FROM "{f.strip()}"' for f in FROM_FILTER]
                query = parts[0]
                for i in range(1, len(parts)):
                    query = f"OR {query} {parts[i]}"
                search_criteria.append(query)
        
        if SUBJECT_FILTER:
            if len(SUBJECT_FILTER) == 1:
                search_criteria.append(f'SUBJECT "{SUBJECT_FILTER[0].strip()}"')
            elif len(SUBJECT_FILTER) == 2:
                search_criteria.append(f'OR SUBJECT "{SUBJECT_FILTER[0].strip()}" SUBJECT "{SUBJECT_FILTER[1].strip()}"')
            else:
                parts = [f'SUBJECT "{s.strip()}"' for s in SUBJECT_FILTER]
                query = parts[0]
                for i in range(1, len(parts)):
                    query = f"OR {query} {parts[i]}"
                search_criteria.append(query)
        
        search_string = " ".join(search_criteria) if search_criteria else "ALL"
        print(f"[*] Поиск: {search_string}\n")
        
        status, message_ids = mail.search(None, search_string)
        
        if status != "OK":
            print("[ERROR] Ошибка поиска")
            return
        
        id_list = message_ids[0].split()
        print(f"[*] Найдено писем: {len(id_list)}\n")
        
        if len(id_list) == 0:
            print("Нет новых писем.")
            return
        
        # Загружаем обработанные письма
        processed_ids = {item['id'] for item in load_processed_emails()}
        
        total_attachments = 0
        skipped_count = 0
        new_count = 0
        
        for i, email_id_bytes in enumerate(id_list, 1):
            email_id_str = email_id_bytes.decode()
            
            # Проверяем, не обработано ли уже
            if email_id_str in processed_ids:
                skipped_count += 1
                continue
            
            new_count += 1
            
            # Получаем письмо
            status, msg_data = mail.fetch(email_id_bytes, "(RFC822)")
            
            if status != "OK":
                continue
            
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            subject = decode_mime_header(msg["Subject"])
            from_addr = decode_mime_header(msg["From"])
            date_str = msg["Date"]
            
            try:
                email_date = datetime(*email.utils.parsedate_tz(date_str)[:6])
            except:
                email_date = None
            
            print(f">>> Письмо {new_count}")
            print(f"    От: {from_addr}")
            print(f"    Тема: {subject}")
            print(f"    Дата: {email_date.strftime('%Y-%m-%d %H:%M:%S') if email_date else 'неизвестно'}")
            print(f"    ID: {email_id_str[:20]}...")
            
            # Сохраняем вложения
            saved = save_attachments(msg, subject, email_date)
            total_attachments += len(saved)
            
            if saved:
                # Отмечаем как обработанное
                mark_email_processed(
                    email_id_str,
                    subject,
                    email_date.strftime('%Y-%m-%d %H:%M:%S') if email_date else ''
                )
                
                # Помечаем как прочитанное
                if MARK_AS_READ:
                    mail.store(email_id_bytes, '+FLAGS', '\\Seen')
                
                # Удаляем письмо, если настроено
                if DELETE_PROCESSED:
                    mail.store(email_id_bytes, '+FLAGS', '\\Deleted')
            
            print()
        
        # Экспанж удалённых писем
        if DELETE_PROCESSED:
            mail.expunge()
        
        print("=" * 60)
        print(f">>> РЕЗУЛЬТАТ:")
        print(f"    Всего найдено: {len(id_list)}")
        print(f"    Пропущено (уже обработано): {skipped_count}")
        print(f"    Новых писем: {new_count}")
        print(f"    Сохранено вложений: {total_attachments}")
        print(f"    Папка: {DOWNLOAD_FOLDER}")
        print("=" * 60)
        
        mail.logout()
        
    except imaplib.IMAP4.error as e:
        print(f"[ERROR] Ошибка IMAP: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Неожиданная ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()