import os
import sys
import django

# Добавляем путь к проекту Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import AdminDev, UserDev

def count_devs():
    """
    Подсчитывает количество UserDev для каждого AdminDev и записывает в total_devs
    """
    try:
        # Получаем всех AdminDev
        admin_devs = AdminDev.objects.all()
        
        for admin_dev in admin_devs:
            # Подсчитываем количество связанных UserDev
            user_dev_count = UserDev.objects.filter(admin=admin_dev).count()
            
            # Обновляем поле total_devs
            admin_dev.total_devs = user_dev_count
            admin_dev.save()
            
            print(f"AdminDev {admin_dev.id} (Twitter: {admin_dev.twitter}): {user_dev_count} UserDev")
            
        print(f"Обновление завершено для {admin_devs.count()} AdminDev")
        
    except Exception as e:
        print(f"Ошибка при подсчете: {e}")

if __name__ == "__main__":
    count_devs()
