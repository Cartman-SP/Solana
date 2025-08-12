import os
import sys
import django

# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import UserDev, AdminDev
from django.db.models import Count

def delete_orphaned_admin_devs():
    """
    Удаляет все AdminDev, к которым не привязан ни один UserDev
    """
    # Находим админов без UserDev
    orphaned_admins = AdminDev.objects.filter(userdev__isnull=True)
    count = orphaned_admins.count()
    
    if count == 0:
        print("Нет AdminDev без UserDev для удаления")
        return
    
    print(f"Найдено {count} AdminDev без UserDev:")
    print("-" * 60)
    
    # Показываем информацию об удаляемых админах
    for i, admin in enumerate(orphaned_admins, 1):
        twitter = admin.twitter if admin.twitter else "Нет Twitter"
        ath = admin.ath
        total_devs = admin.total_devs
        
        print(f"{i:2d}. Twitter: {twitter}")
        print(f"    ATH: {ath}")
        print(f"    Общее количество devs: {total_devs}")
        print("-" * 60)
    
    # Подтверждение удаления
    print(f"\nУдалить {count} AdminDev без UserDev? (y/N): ", end="")
    confirmation = input().strip().lower()
    
    if confirmation == 'y':
        orphaned_admins.delete()
        print(f"Успешно удалено {count} AdminDev без UserDev")
    else:
        print("Удаление отменено")

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
    print("Выберите действие:")
    print("1. Подсчитать админов")
    print("2. Удалить AdminDev без UserDev")
    print("3. Выполнить оба действия")
    print("\nВведите номер (1-3): ", end="")
    
    choice = input().strip()
    
    if choice == "1":
        count_admin_devs()
    elif choice == "2":
        delete_orphaned_admin_devs()
    elif choice == "3":
        print("\n" + "="*60)
        count_admin_devs()
        print("\n" + "="*60)
        delete_orphaned_admin_devs()
    else:
        print("Неверный выбор. Выполняю подсчет админов по умолчанию...")
        count_admin_devs()
