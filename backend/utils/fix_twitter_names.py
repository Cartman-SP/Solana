import os
import sys
import django
import re
from django.db import transaction
from django.db.models import Q

# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import Twitter, Token

def extract_twitter_name(full_name):
    """
    Извлекает правильное имя твитера из строки вида @('0xmeison', 309)
    Возвращает только имя без скобок и количества подписчиков
    """
    # Паттерн для поиска имени в скобках
    pattern = r"@\('([^']+)',\s*\d+\)"
    match = re.match(pattern, full_name)
    
    if match:
        return match.group(1)
    
    # Если паттерн не подошел, попробуем другие варианты
    # Убираем @ в начале, если есть
    if full_name.startswith('@'):
        full_name = full_name[1:]
    
    # Убираем скобки и все после запятой
    if '(' in full_name and ')' in full_name:
        start = full_name.find('(') + 1
        end = full_name.find(',')
        if end == -1:
            end = full_name.find(')')
        if start < end:
            return full_name[start:end].strip("'\"")
    
    # Если ничего не подошло, возвращаем исходную строку без @
    return full_name.strip('@')

def ensure_twitter_name_format(name):
    """
    Убеждается, что имя твитера начинается с @
    """
    if not name.startswith('@'):
        return f"@{name}"
    return name

def fix_twitter_names():
    """
    Основная функция для исправления имен твитеров
    """
    print("Начинаю исправление имен твитеров...")
    
    # Находим все твитеры с неправильным форматом имени
    # Ищем твитеры, которые содержат скобки и запятые (формат @('name', number))
    problematic_twitters = Twitter.objects.filter(
        Q(name__contains='(') & 
        Q(name__contains=',') & 
        Q(name__contains=')')
    )
    
    print(f"Найдено {problematic_twitters.count()} твитеров с неправильным форматом имени")
    
    fixed_count = 0
    errors_count = 0
    
    for twitter in problematic_twitters:
        try:
            old_name = twitter.name
            new_name = extract_twitter_name(old_name)
            
            if not new_name or new_name == old_name:
                print(f"Пропускаю твитер '{old_name}' - не удалось извлечь новое имя")
                continue
            
            # Убеждаемся, что новое имя начинается с @
            new_name = ensure_twitter_name_format(new_name)
            
            print(f"Обрабатываю: '{old_name}' -> '{new_name}'")
            
            with transaction.atomic():
                # Проверяем, существует ли уже твитер с таким именем
                existing_twitter = Twitter.objects.filter(name=new_name).exclude(id=twitter.id).first()
                
                if existing_twitter:
                    print(f"  Найден существующий твитер '{new_name}', перепривязываю токены...")
                    
                    # Перепривязываем все токены к существующему твитеру
                    tokens_to_update = Token.objects.filter(twitter=twitter)
                    tokens_count = tokens_to_update.count()
                    
                    if tokens_count > 0:
                        tokens_to_update.update(twitter=existing_twitter)
                        print(f"  Перепривязано {tokens_count} токенов")
                        
                        # Обновляем счетчики в существующем твитере
                        existing_twitter.total_tokens += twitter.total_tokens
                        existing_twitter.total_trans += twitter.total_trans
                        existing_twitter.total_fees += twitter.total_fees
                        existing_twitter.ath = max(existing_twitter.ath, twitter.ath)
                        existing_twitter.save()
                    
                    # Удаляем проблемный твитер
                    twitter.delete()
                    print(f"  Удален дубликат твитера '{old_name}'")
                    
                else:
                    print(f"  Создаю новый твитер '{new_name}'...")
                    
                    # Создаем новый твитер с правильным именем
                    new_twitter = Twitter.objects.create(
                        name=new_name,
                        blacklist=twitter.blacklist,
                        whitelist=twitter.whitelist,
                        total_tokens=twitter.total_tokens,
                        ath=twitter.ath,
                        total_trans=twitter.total_trans,
                        total_fees=twitter.total_fees,
                        last_autobuy_time=twitter.last_autobuy_time
                    )
                    
                    # Перепривязываем все токены к новому твитеру
                    tokens_to_update = Token.objects.filter(twitter=twitter)
                    tokens_count = tokens_to_update.count()
                    
                    if tokens_count > 0:
                        tokens_to_update.update(twitter=new_twitter)
                        print(f"  Перепривязано {tokens_count} токенов")
                    
                    # Удаляем старый твитер
                    twitter.delete()
                    print(f"  Заменен твитер '{old_name}' на '{new_name}'")
                
                fixed_count += 1
                
        except Exception as e:
            print(f"Ошибка при обработке твитера '{twitter.name}': {e}")
            errors_count += 1
            continue
    
    print(f"\nИсправление завершено!")
    print(f"Успешно исправлено: {fixed_count}")
    print(f"Ошибок: {errors_count}")
    
    # Проверяем, остались ли еще проблемные твитеры
    remaining_problematic = Twitter.objects.filter(
        Q(name__contains='(') & 
        Q(name__contains=',') & 
        Q(name__contains=')')
    ).count()
    
    if remaining_problematic > 0:
        print(f"Осталось проблемных твитеров: {remaining_problematic}")
    else:
        print("Все проблемные твитеры исправлены!")

def fix_all_twitter_names():
    """
    Исправляет все твитеры, добавляя @ в начало, если его нет
    """
    print("Проверяю и исправляю формат всех имен твитеров...")
    
    # Находим все твитеры, которые не начинаются с @
    twitters_without_at = Twitter.objects.filter(~Q(name__startswith='@'))
    
    print(f"Найдено {twitters_without_at.count()} твитеров без @ в начале")
    
    fixed_count = 0
    
    for twitter in twitters_without_at:
        try:
            old_name = twitter.name
            new_name = ensure_twitter_name_format(old_name)
            
            print(f"Исправляю: '{old_name}' -> '{new_name}'")
            
            with transaction.atomic():
                # Проверяем, существует ли уже твитер с таким именем
                existing_twitter = Twitter.objects.filter(name=new_name).exclude(id=twitter.id).first()
                
                if existing_twitter:
                    print(f"  Найден существующий твитер '{new_name}', перепривязываю токены...")
                    
                    # Перепривязываем все токены к существующему твитеру
                    tokens_to_update = Token.objects.filter(twitter=twitter)
                    tokens_count = tokens_to_update.count()
                    
                    if tokens_count > 0:
                        tokens_to_update.update(twitter=existing_twitter)
                        print(f"  Перепривязано {tokens_count} токенов")
                        
                        # Обновляем счетчики в существующем твитере
                        existing_twitter.total_tokens += twitter.total_tokens
                        existing_twitter.total_trans += twitter.total_trans
                        existing_twitter.total_fees += twitter.total_fees
                        existing_twitter.ath = max(existing_twitter.ath, twitter.ath)
                        existing_twitter.save()
                    
                    # Удаляем дубликат
                    twitter.delete()
                    print(f"  Удален дубликат твитера '{old_name}'")
                    
                else:
                    # Просто обновляем имя
                    twitter.name = new_name
                    twitter.save()
                    print(f"  Обновлено имя твитера на '{new_name}'")
                
                fixed_count += 1
                
        except Exception as e:
            print(f"Ошибка при обработке твитера '{twitter.name}': {e}")
            continue
    
    print(f"Исправлено {fixed_count} имен твитеров")

def check_twitter_uniqueness():
    """
    Проверяет уникальность всех твитеров и показывает дубликаты
    """
    print("Проверяю уникальность твитеров...")
    
    # Находим все твитеры
    all_twitters = Twitter.objects.all()
    
    # Создаем словарь для подсчета имен
    name_counts = {}
    duplicate_names = []
    
    for twitter in all_twitters:
        name = twitter.name
        if name in name_counts:
            name_counts[name].append(twitter)
            if name not in duplicate_names:
                duplicate_names.append(name)
        else:
            name_counts[name] = [twitter]
    
    if duplicate_names:
        print(f"Найдено {len(duplicate_names)} дублирующихся имен твитеров:")
        print("-" * 50)
        
        for name in duplicate_names:
            twitters = name_counts[name]
            print(f"'{name}' - {len(twitters)} экземпляров:")
            for twitter in twitters:
                print(f"  ID: {twitter.id}, токенов: {twitter.total_tokens}, ATH: {twitter.ath}")
            print()
        
        return duplicate_names
    else:
        print("Все имена твитеров уникальны!")
        return []

def merge_duplicate_twitters():
    """
    Объединяет дублирующиеся твитеры, оставляя один с наибольшим количеством токенов
    """
    print("Объединяю дублирующиеся твитеры...")
    
    duplicate_names = check_twitter_uniqueness()
    
    if not duplicate_names:
        print("Дубликатов не найдено")
        return
    
    merged_count = 0
    
    for name in duplicate_names:
        try:
            print(f"Обрабатываю дубликаты для '{name}'...")
            
            with transaction.atomic():
                # Получаем все твитеры с этим именем
                twitters = Twitter.objects.filter(name=name).order_by('-total_tokens')
                
                if len(twitters) <= 1:
                    continue
                
                # Оставляем твитер с наибольшим количеством токенов
                main_twitter = twitters[0]
                duplicates = twitters[1:]
                
                print(f"  Основной твитер: ID {main_twitter.id} (токенов: {main_twitter.total_tokens})")
                
                for duplicate in duplicates:
                    print(f"  Объединяю с твитером ID {duplicate.id} (токенов: {duplicate.total_tokens})")
                    
                    # Перепривязываем токены
                    tokens_to_update = Token.objects.filter(twitter=duplicate)
                    tokens_count = tokens_to_update.count()
                    
                    if tokens_count > 0:
                        tokens_to_update.update(twitter=main_twitter)
                        print(f"    Перепривязано {tokens_count} токенов")
                    
                    # Обновляем счетчики в основном твитере
                    main_twitter.total_tokens += duplicate.total_tokens
                    main_twitter.total_trans += duplicate.total_trans
                    main_twitter.total_fees += duplicate.total_fees
                    main_twitter.ath = max(main_twitter.ath, duplicate.ath)
                    
                    # Удаляем дубликат
                    duplicate.delete()
                
                # Сохраняем обновленный основной твитер
                main_twitter.save()
                merged_count += 1
                
        except Exception as e:
            print(f"Ошибка при объединении дубликатов для '{name}': {e}")
            continue
    
    print(f"Объединено {merged_count} групп дубликатов")

def show_problematic_twitters():
    """
    Показывает все твитеры с проблемными именами для предварительного просмотра
    """
    print("Твитеры с проблемными именами:")
    print("-" * 50)
    
    problematic_twitters = Twitter.objects.filter(
        Q(name__contains='(') & 
        Q(name__contains=',') & 
        Q(name__contains=')')
    )
    
    for twitter in problematic_twitters:
        new_name = extract_twitter_name(twitter.name)
        new_name = ensure_twitter_name_format(new_name)
        print(f"'{twitter.name}' -> '{new_name}' (токенов: {twitter.total_tokens})")
    
    print(f"\nВсего найдено: {problematic_twitters.count()}")
    
    # Показываем твитеры без @
    twitters_without_at = Twitter.objects.filter(~Q(name__startswith='@'))
    if twitters_without_at.exists():
        print(f"\nТвитеры без @ в начале: {twitters_without_at.count()}")
        for twitter in twitters_without_at[:10]:  # Показываем первые 10
            new_name = ensure_twitter_name_format(twitter.name)
            print(f"'{twitter.name}' -> '{new_name}'")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Исправление имен твитеров в базе данных')
    parser.add_argument('--preview', action='store_true', help='Только показать проблемные твитеры без исправления')
    parser.add_argument('--fix', action='store_true', help='Выполнить исправление проблемных твитеров')
    parser.add_argument('--fix-all', action='store_true', help='Исправить все имена твитеров (добавить @)')
    parser.add_argument('--check-unique', action='store_true', help='Проверить уникальность твитеров')
    parser.add_argument('--merge-duplicates', action='store_true', help='Объединить дублирующиеся твитеры')
    parser.add_argument('--full-fix', action='store_true', help='Выполнить полное исправление (все опции)')
    
    args = parser.parse_args()
    
    if args.preview:
        show_problematic_twitters()
    elif args.fix:
        fix_twitter_names()
    elif args.fix_all:
        fix_all_twitter_names()
    elif args.check_unique:
        check_twitter_uniqueness()
    elif args.merge_duplicates:
        merge_duplicate_twitters()
    elif args.full_fix:
        print("Выполняю полное исправление...")
        fix_twitter_names()
        fix_all_twitter_names()
        merge_duplicate_twitters()
        print("\nПолное исправление завершено!")
    else:
        print("Используйте один из параметров:")
        print("  --preview         - показать проблемные твитеры")
        print("  --fix             - исправить проблемные твитеры")
        print("  --fix-all         - исправить все имена (добавить @)")
        print("  --check-unique    - проверить уникальность")
        print("  --merge-duplicates - объединить дубликаты")
        print("  --full-fix        - выполнить полное исправление")
        print("\nПримеры:")
        print("  python fix_twitter_names.py --preview")
        print("  python fix_twitter_names.py --full-fix") 