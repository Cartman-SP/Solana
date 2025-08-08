#!/usr/bin/env python3
"""
Быстрый запуск оптимизированной версии process_users.py
"""

import asyncio
import sys
import os
import signal
import time
from typing import Optional

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Импортируем оптимизированный скрипт
from process_users import main, logger, monitor

class OptimizedRunner:
    """Класс для запуска оптимизированной версии с дополнительными возможностями"""
    
    def __init__(self):
        self.running = True
        self.start_time = time.time()
        
    def signal_handler(self, signum, frame):
        """Обработчик сигналов для graceful shutdown"""
        logger.info(f"Получен сигнал {signum}, завершаем работу...")
        self.running = False
        
    async def run_with_monitoring(self):
        """Запуск с расширенным мониторингом"""
        # Устанавливаем обработчики сигналов
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        logger.info("🚀 Запуск ОПТИМИЗИРОВАННОЙ версии process_users.py")
        logger.info("=" * 60)
        
        try:
            # Запускаем основной процесс
            await main()
            
        except KeyboardInterrupt:
            logger.info("⏹️  Получен сигнал прерывания")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
            monitor.log_error(f"Critical error in runner: {e}")
        finally:
            # Финальный отчет
            total_time = time.time() - self.start_time
            logger.info("=" * 60)
            logger.info(f"⏱️  Общее время выполнения: {total_time:.2f} сек")
            logger.info("📊 Финальный отчет о производительности:")
            monitor.print_report()
            logger.info("✅ Завершено")

def main_sync():
    """Синхронная точка входа"""
    runner = OptimizedRunner()
    asyncio.run(runner.run_with_monitoring())

if __name__ == "__main__":
    main_sync() 