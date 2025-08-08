import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

# Список файлов для запуска
files_to_run = [
    'bonk.py',
    'pumpfun.py',
    'main.py',
    'create_db.py',
]

def run_script(script_name):
    try:
        # Запускаем скрипт с тем же интерпретатором, что и текущий
        subprocess.run([sys.executable, script_name], check=True)
        print(f"Скрипт {script_name} успешно завершен")
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при выполнении скрипта {script_name}: {e}")

if __name__ == "__main__":
    print("Запуск всех скриптов...")
    
    # Вариант 1: Последовательный запуск
    # for script in files_to_run:
    #     run_script(script)
    
    # Вариант 2: Параллельный запуск (если скрипты независимы)
    with ThreadPoolExecutor() as executor:
        executor.map(run_script, files_to_run)
    
    print("Все скрипты были запущены")