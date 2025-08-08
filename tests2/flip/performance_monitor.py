import time
import psutil
import asyncio
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """Монитор производительности для отслеживания ресурсов"""
    
    def __init__(self):
        self.start_time = time.time()
        self.metrics = {
            'requests_per_second': 0,
            'memory_usage_mb': 0,
            'cpu_usage_percent': 0,
            'active_connections': 0,
            'errors_count': 0,
            'processed_users': 0,
            'processed_tokens': 0
        }
        self.request_times = []
        self.error_log = []
    
    def start_request(self):
        """Отметить начало запроса"""
        self.request_times.append(time.time())
        # Ограничиваем размер списка
        if len(self.request_times) > 1000:
            self.request_times = self.request_times[-1000:]
    
    def end_request(self):
        """Отметить конец запроса"""
        if self.request_times:
            self.request_times.pop(0)
    
    def log_error(self, error: str):
        """Записать ошибку"""
        self.metrics['errors_count'] += 1
        self.error_log.append({
            'time': time.time(),
            'error': error
        })
        # Ограничиваем размер лога ошибок
        if len(self.error_log) > 100:
            self.error_log = self.error_log[-100:]
    
    def update_metrics(self):
        """Обновить метрики производительности"""
        current_time = time.time()
        elapsed = current_time - self.start_time
        
        # Запросы в секунду
        recent_requests = [t for t in self.request_times if current_time - t < 60]
        self.metrics['requests_per_second'] = len(recent_requests) / 60 if elapsed > 60 else len(recent_requests) / elapsed
        
        # Использование памяти
        process = psutil.Process()
        memory_info = process.memory_info()
        self.metrics['memory_usage_mb'] = memory_info.rss / 1024 / 1024
        
        # Использование CPU
        self.metrics['cpu_usage_percent'] = process.cpu_percent()
        
        # Активные соединения (примерно)
        self.metrics['active_connections'] = len(psutil.net_connections())
    
    def get_report(self) -> Dict:
        """Получить отчет о производительности"""
        self.update_metrics()
        return {
            'elapsed_time': time.time() - self.start_time,
            'metrics': self.metrics.copy(),
            'recent_errors': self.error_log[-10:] if self.error_log else []
        }
    
    def print_report(self):
        """Вывести отчет в консоль"""
        report = self.get_report()
        
        logger.info("=" * 50)
        logger.info("ОТЧЕТ О ПРОИЗВОДИТЕЛЬНОСТИ")
        logger.info("=" * 50)
        logger.info(f"Время выполнения: {report['elapsed_time']:.2f} сек")
        logger.info(f"Запросов в секунду: {report['metrics']['requests_per_second']:.2f}")
        logger.info(f"Использование памяти: {report['metrics']['memory_usage_mb']:.1f} МБ")
        logger.info(f"Использование CPU: {report['metrics']['cpu_usage_percent']:.1f}%")
        logger.info(f"Активных соединений: {report['metrics']['active_connections']}")
        logger.info(f"Обработано пользователей: {report['metrics']['processed_users']}")
        logger.info(f"Обработано токенов: {report['metrics']['processed_tokens']}")
        logger.info(f"Ошибок: {report['metrics']['errors_count']}")
        
        if report['recent_errors']:
            logger.info("Последние ошибки:")
            for error in report['recent_errors']:
                logger.error(f"  {error['error']}")
        
        logger.info("=" * 50)

# Глобальный экземпляр монитора
monitor = PerformanceMonitor()

def log_performance_metrics():
    """Периодический вывод метрик производительности"""
    async def periodic_report():
        while True:
            await asyncio.sleep(60)  # Каждую минуту
            monitor.print_report()
    
    return periodic_report 