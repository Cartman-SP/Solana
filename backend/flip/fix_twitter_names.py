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
        print(f"'{twitter.name}' -> '{new_name}' (токенов: {twitter.total_tokens})")
    
    print(f"\nВсего найдено: {problematic_twitters.count()}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Исправление имен твитеров в базе данных')
    parser.add_argument('--preview', action='store_true', help='Только показать проблемные твитеры без исправления')
    parser.add_argument('--fix', action='store_true', help='Выполнить исправление')
    
    args = parser.parse_args()
    
    if args.preview:
        show_problematic_twitters()
    elif args.fix:
        fix_twitter_names()
    else:
        print("Используйте --preview для просмотра или --fix для исправления")
        print("Пример: python fix_twitter_names.py --preview")
        print("Пример: python fix_twitter_names.py --fix") 