import time
import psutil
import asyncio
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class LoadMonitor:
    """Монитор нагрузки для отслеживания производительности при высокой нагрузке"""
    
    def __init__(self):
        self.start_time = time.time()
        self.metrics = {
            'active_users': 0,
            'active_tokens': 0,
            'requests_per_second': 0,
            'memory_usage_mb': 0,
            'cpu_usage_percent': 0,
            'network_connections': 0,
            'errors_per_minute': 0,
            'average_response_time': 0
        }
        self.response_times = []
        self.error_times = []
        self.user_start_times = {}
        
    def start_user_processing(self, user_id: str):
        """Отметить начало обработки пользователя"""
        self.user_start_times[user_id] = time.time()
        self.metrics['active_users'] += 1
        
    def end_user_processing(self, user_id: str):
        """Отметить завершение обработки пользователя"""
        if user_id in self.user_start_times:
            processing_time = time.time() - self.user_start_times[user_id]
            self.response_times.append(processing_time)
            del self.user_start_times[user_id]
            self.metrics['active_users'] -= 1
            
            # Ограничиваем размер списка
            if len(self.response_times) > 1000:
                self.response_times = self.response_times[-1000:]
    
    def log_response_time(self, response_time: float):
        """Записать время ответа"""
        self.response_times.append(response_time)
        if len(self.response_times) > 1000:
            self.response_times = self.response_times[-1000:]
    
    def log_error(self):
        """Записать ошибку"""
        self.error_times.append(time.time())
        # Ограничиваем размер списка
        if len(self.error_times) > 100:
            self.error_times = self.error_times[-100:]
    
    def update_metrics(self):
        """Обновить метрики нагрузки"""
        current_time = time.time()
        elapsed = current_time - self.start_time
        
        # Запросы в секунду
        recent_requests = [t for t in self.response_times if current_time - t < 60]
        self.metrics['requests_per_second'] = len(recent_requests) / 60 if elapsed > 60 else len(recent_requests) / elapsed
        
        # Среднее время ответа
        if self.response_times:
            self.metrics['average_response_time'] = sum(self.response_times) / len(self.response_times)
        
        # Ошибки в минуту
        recent_errors = [t for t in self.error_times if current_time - t < 60]
        self.metrics['errors_per_minute'] = len(recent_errors)
        
        # Использование ресурсов
        process = psutil.Process()
        memory_info = process.memory_info()
        self.metrics['memory_usage_mb'] = memory_info.rss / 1024 / 1024
        self.metrics['cpu_usage_percent'] = process.cpu_percent()
        
        # Сетевые соединения
        try:
            self.metrics['network_connections'] = len(psutil.net_connections())
        except:
            self.metrics['network_connections'] = 0
    
    def get_load_report(self) -> Dict:
        """Получить отчет о нагрузке"""
        self.update_metrics()
        return {
            'elapsed_time': time.time() - self.start_time,
            'metrics': self.metrics.copy(),
            'active_users_count': len(self.user_start_times),
            'total_processed': len(self.response_times)
        }
    
    def print_load_report(self):
        """Вывести отчет о нагрузке"""
        report = self.get_load_report()
        
        logger.info("=" * 60)
        logger.info("📊 ОТЧЕТ О НАГРУЗКЕ (50 пользователей)")
        logger.info("=" * 60)
        logger.info(f"⏱️  Время выполнения: {report['elapsed_time']:.2f} сек")
        logger.info(f"👥 Активных пользователей: {report['metrics']['active_users']}")
        logger.info(f"🔄 Запросов в секунду: {report['metrics']['requests_per_second']:.2f}")
        logger.info(f"⚡ Среднее время ответа: {report['metrics']['average_response_time']:.3f} сек")
        logger.info(f"💾 Использование памяти: {report['metrics']['memory_usage_mb']:.1f} МБ")
        logger.info(f"🖥️  Использование CPU: {report['metrics']['cpu_usage_percent']:.1f}%")
        logger.info(f"🌐 Сетевых соединений: {report['metrics']['network_connections']}")
        logger.info(f"❌ Ошибок в минуту: {report['metrics']['errors_per_minute']}")
        logger.info(f"📈 Всего обработано: {report['total_processed']}")
        logger.info("=" * 60)
        
        # Предупреждения о высокой нагрузке
        if report['metrics']['cpu_usage_percent'] > 80:
            logger.warning("⚠️  ВЫСОКАЯ НАГРУЗКА CPU!")
        if report['metrics']['memory_usage_mb'] > 1000:
            logger.warning("⚠️  ВЫСОКОЕ ИСПОЛЬЗОВАНИЕ ПАМЯТИ!")
        if report['metrics']['errors_per_minute'] > 10:
            logger.warning("⚠️  МНОГО ОШИБОК!")

# Глобальный экземпляр монитора нагрузки
load_monitor = LoadMonitor()

async def monitor_load_periodically():
    """Периодический мониторинг нагрузки"""
    while True:
        await asyncio.sleep(30)  # Каждые 30 секунд
        load_monitor.print_load_report() 