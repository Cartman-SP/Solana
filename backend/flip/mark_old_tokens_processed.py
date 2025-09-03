import os
import sys
import django
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q

# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import Token


def mark_old_tokens_processed():
    """
    Устанавливает processed = True всем токенам:
    1. Старше 40 часов (все, независимо от community_id)
    2. Без community_id (все, независимо от возраста)
    """
    # Вычисляем время 40 часов назад
    cutoff_time = timezone.now() - timedelta(hours=40)
    
    # Находим токены для обновления:
    # 1. Старше 40 часов (все)
    # 2. Без community_id (все)
    tokens_to_update = Token.objects.filter(
        Q(created_at__lt=cutoff_time) | Q(community_id__isnull=True),
        processed=False
    ).distinct()
    
    # Получаем количество токенов для обновления
    count = tokens_to_update.count()
    
    if count == 0:
        print("Нет токенов для обновления.")
        return
    
    # Подсчитываем отдельно каждую категорию
    old_tokens_count = Token.objects.filter(
        created_at__lt=cutoff_time,
        processed=False
    ).count()
    
    no_community_count = Token.objects.filter(
        community_id__isnull=True,
        processed=False
    ).count()
    
    print(f"Найдено {count} токенов для обновления:")
    print(f"- Старше 40 часов: {old_tokens_count} токенов")
    print(f"- Без community_id: {no_community_count} токенов")
    print(f"- Общее количество (с учетом пересечений): {count} токенов")
    print(f"- Время отсечения: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Показываем примеры токенов
    sample_tokens = tokens_to_update[:5]
    print(f"\nПримеры токенов:")
    for token in sample_tokens:
        age_hours = (timezone.now() - token.created_at).total_seconds() / 3600
        has_community = "Да" if token.community_id else "Нет"
        print(f"  - {token.address}")
        print(f"    Возраст: {age_hours:.1f} часов")
        print(f"    Community ID: {has_community}")
        print(f"    Создан: {token.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
    
    if count > 5:
        print(f"  ... и еще {count - 5} токенов")
    
    # Запрашиваем подтверждение
    response = input(f"\nПродолжить обновление {count} токенов? (y/N): ")
    
    if response.lower() != 'y':
        print("Операция отменена.")
        return
    
    # Выполняем обновление
    try:
        updated_count = tokens_to_update.update(processed=True)
        print(f"\n✅ Успешно обновлено {updated_count} токенов!")
        
        # Показываем статистику
        total_tokens = Token.objects.count()
        processed_tokens = Token.objects.filter(processed=True).count()
        unprocessed_tokens = Token.objects.filter(processed=False).count()
        
        print(f"\nСтатистика после обновления:")
        print(f"- Всего токенов: {total_tokens}")
        print(f"- Обработано (processed=True): {processed_tokens}")
        print(f"- Не обработано (processed=False): {unprocessed_tokens}")
        
    except Exception as e:
        print(f"❌ Ошибка при обновлении: {e}")


def show_token_statistics():
    """Показывает статистику по токенам"""
    total_tokens = Token.objects.count()
    processed_tokens = Token.objects.filter(processed=True).count()
    unprocessed_tokens = Token.objects.filter(processed=False).count()
    
    # Токены без community_id
    no_community_tokens = Token.objects.filter(community_id__isnull=True).count()
    
    # Токены старше 40 часов
    cutoff_time = timezone.now() - timedelta(hours=40)
    old_tokens = Token.objects.filter(created_at__lt=cutoff_time).count()
    
    # Токены старше 40 часов без community_id и processed=False
    target_tokens = Token.objects.filter(
        Q(created_at__lt=cutoff_time) | Q(community_id__isnull=True),
        processed=False
    ).distinct().count()
    
    print("📊 Статистика токенов:")
    print(f"- Всего токенов: {total_tokens}")
    print(f"- Обработано (processed=True): {processed_tokens}")
    print(f"- Не обработано (processed=False): {unprocessed_tokens}")
    print(f"- Без community_id: {no_community_tokens}")
    print(f"- Старше 40 часов: {old_tokens}")
    print(f"- Целевые для обновления: {target_tokens}")


if __name__ == "__main__":
    print("🔧 Скрипт для установки processed = True токенам")
    print("=" * 60)
    print("Обновляет все токены старше 40 часов И все токены без community_id")
    print()
    
    # Показываем текущую статистику
    show_token_statistics()
    print()
    
    # Запускаем основную функцию
    mark_old_tokens_processed() 