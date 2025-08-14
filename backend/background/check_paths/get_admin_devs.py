import os
import sys
import django

# Добавляем путь к проекту Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import AdminDev, UserDev

def main() -> None:
    admin_twitter = "admin_b0c033f2"

    admin = AdminDev.objects.get(twitter=admin_twitter)
    user_devs = UserDev.objects.filter(admin=admin)

    addresses = [user_dev.adress for user_dev in user_devs]
    content = "[" + ", ".join([f"'{addr}'" for addr in addresses]) + "]"

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    output_path = os.path.join(project_root, "devs.txt")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    main()
