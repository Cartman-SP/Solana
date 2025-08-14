import os
import sys
import django

# Добавляем путь к проекту Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import AdminDev, UserDev

def clean_user_devs():
    """
    Очищает все записи UserDev:
    - устанавливает admin = None
    - устанавливает faunded = False
    """
    try:
        # Получаем количество записей до очистки
        total_count = UserDev.objects.count()
        print(f"Найдено записей UserDev: {total_count}")
        
        if total_count == 0:
            print("Нет записей для очистки")
            return
        
        # Обновляем все записи UserDev
        updated_count = UserDev.objects.update(
            admin=None,
            faunded=False
        )
        
        print(f"Успешно обновлено записей: {updated_count}")
        print("Все записи UserDev очищены:")
        print("- admin установлен в None")
        print("- faunded установлен в False")
        
    except Exception as e:
        print(f"Ошибка при очистке базы данных: {e}")

if __name__ == "__main__":
    print("Начинаю очистку базы данных...")
    clean_user_devs()
    print("Очистка завершена!")
