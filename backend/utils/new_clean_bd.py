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
        print(f"Ошибка при очистке UserDev: {e}")

def delete_admin_devs():
    """
    Удаляет всех AdminDev из базы данных
    """
    try:
        # Получаем количество записей до удаления
        total_count = AdminDev.objects.count()
        print(f"Найдено записей AdminDev: {total_count}")
        
        if total_count == 0:
            print("Нет записей AdminDev для удаления")
            return
        
        # Удаляем все записи AdminDev
        deleted_count = AdminDev.objects.all().delete()
        # delete() возвращает кортеж (количество_удаленных_объектов, словарь_с_количеством_по_типам)
        actual_deleted = deleted_count[0]
        
        print(f"Успешно удалено записей AdminDev: {actual_deleted}")
        
    except Exception as e:
        print(f"Ошибка при удалении AdminDev: {e}")

def delete_user_devs_with_zero_tokens():
    """
    Удаляет всех UserDev у которых total_tokens = 0
    """
    try:
        # Получаем количество записей с total_tokens = 0
        zero_tokens_count = UserDev.objects.filter(total_tokens=0).count()
        print(f"Найдено UserDev с total_tokens = 0: {zero_tokens_count}")
        
        if zero_tokens_count == 0:
            print("Нет UserDev с total_tokens = 0 для удаления")
            return
        
        # Удаляем все записи UserDev с total_tokens = 0
        deleted_count = UserDev.objects.filter(total_tokens=0).delete()
        actual_deleted = deleted_count[0]
        
        print(f"Успешно удалено UserDev с total_tokens = 0: {actual_deleted}")
        
    except Exception as e:
        print(f"Ошибка при удалении UserDev с total_tokens = 0: {e}")

def run_full_cleanup():
    """
    Выполняет полную очистку базы данных
    """
    print("=== НАЧАЛО ПОЛНОЙ ОЧИСТКИ БАЗЫ ДАННЫХ ===")
    
    # 1. Очищаем UserDev (устанавливаем admin = None, faunded = False)
    print("\n1. Очистка UserDev...")
    clean_user_devs()
    
    # 2. Удаляем всех AdminDev
    print("\n2. Удаление AdminDev...")
    delete_admin_devs()
    
    # 3. Удаляем UserDev с total_tokens = 0
    print("\n3. Удаление UserDev с total_tokens = 0...")
    delete_user_devs_with_zero_tokens()
    
    print("\n=== ПОЛНАЯ ОЧИСТКА ЗАВЕРШЕНА ===")

if __name__ == "__main__":
    print("Выберите действие:")
    print("1 - Очистить UserDev (admin=None, faunded=False)")
    print("2 - Удалить всех AdminDev")
    print("3 - Удалить UserDev с total_tokens = 0")
    print("4 - Выполнить полную очистку")
    
    choice = input("Введите номер (1-4): ").strip()
    
    if choice == "1":
        clean_user_devs()
    elif choice == "2":
        delete_admin_devs()
    elif choice == "3":
        delete_user_devs_with_zero_tokens()
    elif choice == "4":
        run_full_cleanup()
    else:
        print("Неверный выбор. Запускаю полную очистку по умолчанию...")
        run_full_cleanup()
