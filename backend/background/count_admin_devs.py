import os
import sys
import django

# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import UserDev, AdminDev
from django.db.models import Count

def count_admin_devs():
    """
    Подсчитывает количество UserDev для каждого админа и выводит топ-20
    """
    # Получаем админов с количеством UserDev, сортируем по убыванию
    admin_counts = AdminDev.objects.annotate(
        dev_count=Count('userdev')
    ).order_by('-dev_count')[:20]
    
    print("Топ-20 админов с наибольшим количеством UserDev:")
    print("-" * 60)
    
    for i, admin in enumerate(admin_counts, 1):
        twitter = admin.twitter if admin.twitter else "Нет Twitter"
        dev_count = admin.dev_count
        ath = admin.ath
        
        print(f"{i:2d}. Twitter: {twitter}")
        print(f"    Количество UserDev: {dev_count}")
        print(f"    ATH: {ath}")
        print("-" * 60)
    
    # Общая статистика
    total_admins = AdminDev.objects.count()
    total_userdevs = UserDev.objects.count()
    admins_with_devs = AdminDev.objects.filter(userdev__isnull=False).distinct().count()
    
    print(f"\nОбщая статистика:")
    print(f"Всего админов: {total_admins}")
    print(f"Всего UserDev: {total_userdevs}")
    print(f"Админов с UserDev: {admins_with_devs}")

if __name__ == "__main__":
    count_admin_devs()
