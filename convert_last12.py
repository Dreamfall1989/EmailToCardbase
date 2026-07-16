import csv
import os
from datetime import datetime

def hex_to_z2(hex_str):
    """
    Конвертирует HEX-номер карты в формат Z2.
    Берет последние 12 символов (6 байт) и переводит в десятичное число.
    """
    hex_str = hex_str.strip().upper()
    
    # Берем последние 12 символов
    if len(hex_str) >= 12:
        last_12 = hex_str[-12:]
    else:
        # Если меньше 12 символов, дополняем слева нулями
        last_12 = hex_str.zfill(12)
    
    # Конвертируем HEX в десятичное число
    decimal_value = int(last_12, 16)
    
    # Возвращаем как строку без ведущих нулей
    return str(decimal_value)


def read_csv_with_encoding(input_csv):
    """Читает CSV с автоматическим определением кодировки"""
    encodings = ['utf-8', 'windows-1251', 'cp1251', 'latin-1', 'cp866']
    
    for enc in encodings:
        try:
            with open(input_csv, "r", encoding=enc) as infile:
                # Пробуем разные разделители
                for delim in [';', ',', '\t']:
                    try:
                        infile.seek(0)
                        reader = csv.reader(infile, delimiter=delim)
                        header = next(reader)
                        print(f"Кодировка: {enc}, разделитель: '{delim}'")
                        
                        rows = []
                        for row in reader:
                            if len(row) >= 1:
                                hex_number = row[0].strip()
                                if hex_number:
                                    rows.append(hex_number)
                        return rows
                    except (StopIteration, csv.Error):
                        continue
        except (UnicodeDecodeError, StopIteration):
            continue
    
    raise Exception("Не удалось прочитать файл")


def process_files():
    # Ищем все CSV файлы в текущей папке
    csv_files = [f for f in os.listdir('.') if f.lower().endswith('.csv')]
    
    if not csv_files:
        print("Ошибка: CSV файлы не найдены в текущей папке!")
        return
    
    # Берем первый найденный CSV файл
    input_csv = csv_files[0]
    print(f"Найден файл: {input_csv}")
    
    # Создаем имя выходного файла с текущей датой и временем
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_txt = f"{timestamp}.txt"
    
    print(f"Выходной файл: {output_txt}")
    print("-" * 50)
    
    # Читаем данные
    hex_numbers = read_csv_with_encoding(input_csv)
    print(f"Всего строк: {len(hex_numbers)}\n")
    
    results = []
    skipped = 0
    
    for hex_original in hex_numbers:
        hex_clean = hex_original.replace(" ", "").replace("-", "").upper()
        
        if not hex_clean:
            print(f"ПРОПУЩЕН (пустая строка): {hex_original}")
            skipped += 1
            continue
            
        try:
            z2 = hex_to_z2(hex_clean)
            # Формат: Z2,01.07.2055,3,,,ИСХОДНЫЙ_HEX,2,200
            line = f"{z2},01.07.2055,3,,,{hex_original},2,500"
            results.append(line)
            
            # Для отладки показываем преобразование (первые 5)
            if len(results) <= 5:
                last_12 = hex_clean[-12:] if len(hex_clean) >= 12 else hex_clean.zfill(12)
                print(f"DEBUG: {hex_clean} -> {last_12} -> {z2}")
                
        except ValueError as e:
            print(f"ПРОПУЩЕН ({e}): {hex_original}")
            skipped += 1
    
    # Показываем первые 5 для проверки
    print("\nПервые 5 строк:")
    for i in range(min(5, len(results))):
        print(f"  {results[i]}")
    
    # Записываем в ANSI
    with open(output_txt, "w", encoding="windows-1251") as outfile:
        for line in results:
            outfile.write(line + "\n")
    
    print(f"\nГотово! Записано: {len(results)}, пропущено: {skipped}")
    print(f"Результат сохранен в: {output_txt}")


if __name__ == "__main__":
    process_files()