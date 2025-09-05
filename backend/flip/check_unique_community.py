import os
import sys
import django
from collections import defaultdict
from datetime import datetime

# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import Token

def check_unique_community():
    """
    Проверяет уникальность community токенов и обновляет поле unique_community.
    Если токен самый старый для данной community, то unique_community = True.
    """
    print("Начинаем проверку уникальности community токенов...")
    
    # Получаем все токены с community_id, отсортированные по дате создания
    tokens = Token.objects.filter(
        community_id__isnull=False,
        community_id__gt=''  # Исключаем пустые строки
    ).order_by('created_at')
    
    print(f"Найдено {tokens.count()} токенов с community_id")
    
    # Группируем токены по community_id
    community_groups = defaultdict(list)
    
    for token in tokens:
        community_groups[token.community_id].append(token)
    
    print(f"Найдено {len(community_groups)} уникальных community")
    
    updated_count = 0
    
    # Обрабатываем каждую группу community
    for community_id, community_tokens in community_groups.items():
        print(f"\nОбрабатываем community: {community_id} ({len(community_tokens)} токенов)")
        
        # Сортируем токены в группе по дате создания (от старых к новым)
        community_tokens.sort(key=lambda x: x.created_at)
        
        # Самый старый токен всегда уникальный
        oldest_token = community_tokens[0]
        if not oldest_token.unique_community:
            oldest_token.unique_community = True
            oldest_token.save()
            updated_count += 1
            print(f"  ✓ Самый старый токен {oldest_token.address} помечен как уникальный")
        
        # Проверяем остальные токены на уникальность
        for i, token in enumerate(community_tokens[1:], 1):
            # Проверяем, есть ли более старые токены с таким же community_id
            has_older_tokens = any(
                older_token.community_id == token.community_id and 
                older_token.created_at < token.created_at
                for older_token in community_tokens[:i]
            )
            
            # Токен уникальный, если нет более старых токенов с таким же community_id
            is_unique = not has_older_tokens
            
            if token.unique_community != is_unique:
                token.unique_community = is_unique
                token.save()
                updated_count += 1
                status = "уникальный" if is_unique else "не уникальный"
                print(f"  ✓ Токен {token.address} помечен как {status}")
    
    print(f"\nПроверка завершена. Обновлено {updated_count} токенов.")
    
    # Выводим статистику
    total_tokens = Token.objects.filter(community_id__isnull=False, community_id__gt='').count()
    unique_tokens = Token.objects.filter(community_id__isnull=False, community_id__gt='', unique_community=True).count()
    non_unique_tokens = total_tokens - unique_tokens
    
    print(f"\nСтатистика:")
    print(f"  Всего токенов с community_id: {total_tokens}")
    print(f"  Уникальных токенов: {unique_tokens}")
    print(f"  Не уникальных токенов: {non_unique_tokens}")

def show_community_statistics():
    """Показывает статистику по community токенам"""
    print("\n=== Статистика по community ===")
    
    # Группируем токены по community_id
    community_stats = {}
    
    tokens = Token.objects.filter(
        community_id__isnull=False,
        community_id__gt=''
    ).order_by('created_at')
    
    for token in tokens:
        community_id = token.community_id
        if community_id not in community_stats:
            community_stats[community_id] = {
                'total': 0,
                'unique': 0,
                'oldest_token': None,
                'tokens': []
            }
        
        community_stats[community_id]['total'] += 1
        community_stats[community_id]['tokens'].append(token)
        
        if token.unique_community:
            community_stats[community_id]['unique'] += 1
        
        # Запоминаем самый старый токен
        if (community_stats[community_id]['oldest_token'] is None or 
            token.created_at < community_stats[community_id]['oldest_token'].created_at):
            community_stats[community_id]['oldest_token'] = token
    
    # Сортируем по количеству токенов (убывание)
    sorted_communities = sorted(
        community_stats.items(), 
        key=lambda x: x[1]['total'], 
        reverse=True
    )
    
    print(f"Топ-10 community по количеству токенов:")
    for i, (community_id, stats) in enumerate(sorted_communities[:10], 1):
        oldest_date = stats['oldest_token'].created_at.strftime('%Y-%m-%d %H:%M:%S')
        print(f"  {i}. {community_id}: {stats['total']} токенов, {stats['unique']} уникальных")
        print(f"     Самый старый: {stats['oldest_token'].address} ({oldest_date})")

if __name__ == "__main__":
    print("=== Скрипт проверки уникальности community токенов ===")
    print(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Проверяем уникальность
        check_unique_community()
        
        # Показываем статистику
        show_community_statistics()
        
    except Exception as e:
        print(f"Ошибка при выполнении скрипта: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\nСкрипт завершен: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")