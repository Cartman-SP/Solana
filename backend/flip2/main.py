import asyncio
import subprocess
import sys
import os
import signal
import time

class ProcessManager:
    def __init__(self):
        self.processes = []
        self.running = True
        
    def start_process(self, script_name, description):
        """Запускает процесс"""
        try:
            script_path = os.path.join(os.path.dirname(__file__), script_name)
            process = subprocess.Popen(
                [sys.executable, script_path],
                stdout=None,  # Используем stdout родительского процесса
                stderr=None,  # Используем stderr родительского процесса
                universal_newlines=True,
                bufsize=0  # Отключаем буферизацию
            )
            self.processes.append((process, description))
            print(f"✅ Запущен {description} (PID: {process.pid})")
            return process
        except Exception as e:
            print(f"❌ Ошибка запуска {description}: {e}")
            return None
    
    def start_all_processes(self):
        """Запускает все процессы"""
        print("🚀 Запуск всех программ...")
        
        # Запускаем веб-сокет сервер
        self.start_process("websocket_server.py", "Веб-сокет сервер")
        time.sleep(2)  # Даем время серверу запуститься
        
        # Запускаем отправителей
        self.start_process("pumpfun.py", "PumpFun монитор")
        
        # Запускаем получателей
        #self.start_process("live.py", "Live получатель")
        self.start_process("create.py", "Create получатель")
        
        print("\n📊 Все программы запущены!")
        print("💡 Для остановки нажмите Ctrl+C")
    
    def stop_all_processes(self):
        """Останавливает все процессы"""
        print("\n🛑 Остановка всех программ...")
        self.running = False
        
        for process, description in self.processes:
            try:
                process.terminate()
                process.wait(timeout=5)
                print(f"✅ Остановлен {description}")
            except subprocess.TimeoutExpired:
                process.kill()
                print(f"⚠️ Принудительно остановлен {description}")
            except Exception as e:
                print(f"❌ Ошибка остановки {description}: {e}")
    
    def monitor_processes(self):
        """Мониторит процессы и выводит их вывод"""
        while self.running:
            for process, description in self.processes[:]:
                if process.poll() is not None:
                    # Процесс завершился
                    self.processes.remove((process, description))
                    print(f"⚠️ Процесс {description} завершился")
                    
                    # Перезапускаем процесс
                    if self.running:
                        print(f"🔄 Перезапуск {description}...")
                        script_name = description.split()[0].lower() + ".py"
                        if description == "Веб-сокет сервер":
                            script_name = "websocket_server.py"
                        new_process = self.start_process(script_name, description)
                        if new_process:
                            self.processes.append((new_process, description))
            
            time.sleep(1)  # Возвращаем нормальную задержку
    
    def signal_handler(self, signum, frame):
        """Обработчик сигнала для корректного завершения"""
        print("\n📡 Получен сигнал завершения...")
        self.stop_all_processes()
        sys.exit(0)

def main():
    # Регистрируем обработчик сигналов
    signal.signal(signal.SIGINT, lambda s, f: None)
    
    manager = ProcessManager()
    manager.signal_handler = manager.signal_handler
    signal.signal(signal.SIGINT, manager.signal_handler)
    
    try:
        # Запускаем все процессы
        manager.start_all_processes()
        
        # Мониторим их работу
        manager.monitor_processes()
        
    except KeyboardInterrupt:
        manager.signal_handler(signal.SIGINT, None)
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        manager.stop_all_processes()

if __name__ == "__main__":
    main() 