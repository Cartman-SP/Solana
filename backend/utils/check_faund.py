import os
import sys
import django
import argparse

# Добавляем путь к проекту Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import UserDev


def find_founded_devs_by_address(wallet_address: str):
    """
    По указанному адресу кошелька находит(ят) запись(и) UserDev и выводит всех UserDev,
    у кого поле faunded_by указывает на найденного(ых) пользователя(ей).
    """
    base_users = list(UserDev.objects.filter(adress=wallet_address))

    if not base_users:
        print(f"UserDev с адресом '{wallet_address}' не найден")
        return 1

    total_children = 0
    for base_user in base_users:
        children = list(UserDev.objects.filter(faunded_by=base_user))
        total_children += len(children)

        print("-" * 60)
        print(f"Базовый UserDev: id={base_user.id}, address={base_user.adress}")
        print(f"Найдено зависимых (faunded_by): {len(children)}")
        if children:
            for child in children:
                print(
                    f"  • id={child.id}; address={child.adress}; "
                    f"total_tokens={child.total_tokens}; whitelist={child.whitelist}; "
                    f"blacklist={child.blacklist}; ath={child.ath}"
                )

    if len(base_users) > 1:
        print("-" * 60)
        print(f"Всего базовых записей по адресу {wallet_address}: {len(base_users)}")
        print(f"Суммарно зависимых записей: {total_children}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Найти UserDev, которые были faunded_by указанного адреса кошелька"
    )
    parser.add_argument(
        "address",
        nargs='?',
        help="Адрес кошелька (значение поля 'adress' модели UserDev)"
    )
    parser.add_argument(
        "--address",
        dest="address_opt",
        help="Адрес кошелька (альтернативный способ передачи)"
    )

    args = parser.parse_args()
    wallet_address = args.address_opt or args.address

    if not wallet_address:
        print("Укажите адрес кошелька как позиционный аргумент или через --address")
        return 2

    return find_founded_devs_by_address(wallet_address)


if __name__ == "__main__":
    raise SystemExit(main())
