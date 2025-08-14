import django
import sys
import os
import requests
import asyncio
import time
import uuid
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import random
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import UserDev, AdminDev
from asgiref.sync import sync_to_async

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjcmVhdGVkQXQiOjE3NTM1NzAxNzU2MjEsImVtYWlsIjoiZGFuaWlsLnNoaXJraW4wMDVAZ21haWwuY29tIiwiYWN0aW9uIjoidG9rZW4tYXBpIiwiYXBpVmVyc2lvbiI6InYyIiwiaWF0IjoxNzUzNTcwMTc1fQ.W2-ic8rt8wQZptdygjc6F3Z5N8CJv1UrCkfqzdwq2vw"

# Глобальные переменные для отслеживания API запросов
api_request_count = 0
last_reset_time = time.time()
MAX_REQUESTS_PER_MINUTE = 1000

def check_api_limit():
    """Проверяет лимит API запросов и ждет при необходимости"""
    global api_request_count, last_reset_time
    
    current_time = time.time()
    
    # Сброс счетчика каждую минуту
    if current_time - last_reset_time >= 60:
        api_request_count = 0
        last_reset_time = current_time
    
    # Если достигнут лимит, ждем до следующей минуты
    if api_request_count >= MAX_REQUESTS_PER_MINUTE:
        wait_time = 60 - (current_time - last_reset_time)
        if wait_time > 0:
            print(f"Достигнут лимит API ({MAX_REQUESTS_PER_MINUTE} запросов/мин). Ждем {wait_time:.2f} секунд...")
            time.sleep(wait_time)
            api_request_count = 0
            last_reset_time = time.time()

def make_api_request(url, headers, max_retries=3):
    """Выполняет API запрос с обработкой ошибок и перезапусками"""
    global api_request_count
    
    for attempt in range(max_retries):
        try:
            check_api_limit()
            
            response = requests.get(url, headers=headers, timeout=30)
            api_request_count += 1
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:  # Rate limit exceeded
                print(f"Rate limit exceeded. Попытка {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(1, 5)  # Exponential backoff
                    time.sleep(wait_time)
                    continue
            else:
                print(f"API ошибка {response.status_code}: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"Ошибка запроса (попытка {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(random.uniform(1, 3))
                continue
        except Exception as e:
            print(f"Неожиданная ошибка (попытка {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(random.uniform(1, 3))
                continue
    
    print(f"Не удалось выполнить API запрос после {max_retries} попыток")
    return None


def minutes_since(timestamp_str):
    # Парсим строку времени (предполагается формат ISO 8601 с Z на конце)
    past_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    
    # Получаем текущее время в UTC
    current_time = datetime.now(timezone.utc)
    
    # Вычисляем разницу
    time_diff = current_time - past_time
    
    # Преобразуем разницу в минуты
    return time_diff.total_seconds() / 60


def check_birzh(address, tags):
    if "exchange_wallet" in tags or "deposit_address" in tags:
        return True
    
    base_url = "https://pro-api.solscan.io/v2.0/account/"
    url = f"{base_url}transfer?address={address}&activity_type[]=ACTIVITY_SPL_TRANSFER&page=1&page_size=100&sort_by=block_time&sort_order=desc"    
    headers = {"token": API_KEY}
    
    response = make_api_request(url, headers)
    if response is None:
        return False
    
    data = response.get('data', [])
    if not data:
        return False
    
    try:
        ago = minutes_since(data[10]['time'])
    except:
        ago = minutes_since(data[-1]['time'])

    if ago < 6 and len(data) == 100:
        return True

    url = f"{base_url}portfolio?address={address}&exclude_low_score_tokens=true"    
    response = make_api_request(url, headers)
    if response is None:
        return False
    
    data = response.get('data', [])
    try:
        balance = data.get("total_value", {})
    except:
        balance = 0
    
    if balance > 30000:
        return True
    return False

def get_funding_addresses(wallet_address):
    base_url = "https://pro-api.solscan.io/v2.0/account/metadata"
    
    headers = {
        "token": API_KEY,
        "User-Agent": "SolanaFlipper/1.0"
    }
    
    # Формируем URL для входящих трансферов (flow=in), чтобы получить только фондирующие адреса
    url = f"{base_url}?address={wallet_address}"
    
    data = make_api_request(url, headers)
    if data is None:
        return {}
    
    data = data.get('data', {})
    return data


def process_fund(address):
    arr = []
    count = 0
    arr.append(UserDev.objects.get(adress = address))
    fund = address
    while True:
        data = get_funding_addresses(fund)
        if not data or 'funded_by' not in data or 'funded_by' not in data['funded_by']:
            break
            
        fund = data['funded_by']['funded_by']
        tags = []
        try:
            tags = data['account_tags']
        except:
            pass    
        if check_birzh(fund, tags):
            unique_twitter = f"admin_{uuid.uuid4().hex[:8]}"
            admin = AdminDev.objects.create(twitter=unique_twitter)
            return arr, admin
        dev, created = UserDev.objects.get_or_create(
            adress=fund,
            faunded=True,
        )
        if created:
            arr.append(dev)
            count += 1
        else:
            if dev.admin:
                return arr, dev.admin
            else:
                unique_twitter = f"admin_{uuid.uuid4().hex[:8]}"
                admin = AdminDev.objects.create(twitter=unique_twitter)
                arr.append(dev)
                return arr, admin
    unique_twitter = f"admin_{uuid.uuid4().hex[:8]}"
    admin = AdminDev.objects.create(twitter=unique_twitter)
    return arr, admin
    
def process_first(address):
    try:
        arr, admin = process_fund(address)
        
        if not admin:
            print(f"Не удалось создать AdminDev для адреса {address}")
            return [], None
            
        # Сохраняем admin если он еще не сохранен
        if not admin.id:
            admin.save()
        
        total_tokens = 0# Обновляем все UserDev в массиве
        for i in range(len(arr)):
            total_tokens += arr[i].total_tokens
            arr[i].admin = admin
            arr[i].faunded = True
            try:
                arr[i].faunded_by = arr[i+1]
            except:
                pass
            arr[i].save()
        
        admin.total_tokens += total_tokens# Обновляем total_devs у AdminDev
        admin.total_devs += len(arr)
        admin.save()
        
        return arr, admin
    except Exception as e:
        print(f"Ошибка при обработке адреса {address}: {e}")
        return [], None

def process_dev_async(address):
    """Асинхронная обработка одного dev"""
    try:
        print(f"Обрабатываю адрес: {address}")
        result = process_first(address)
        print(f"Успешно обработан адрес: {address}")
        return result
    except Exception as e:
        print(f"Ошибка при асинхронной обработке адреса {address}: {e}")
        return None

def main():
    """Основная функция с бесконечным циклом"""
    print("Запуск основного цикла обработки...")
    
    while True:
        try:
            # Получаем 50 UserDev которые не в blacklist и у которых faunded = False
            unprocessed_devs = UserDev.objects.filter(
                blacklist=False,
                faunded=False
            ).order_by('-id')[:100]
            
            if not unprocessed_devs.exists():
                print("Нет необработанных dev'ов. Ждем 60 секунд...")
                time.sleep(60)
                continue
            
            print(f"Найдено {unprocessed_devs.count()} необработанных dev'ов")
            
            # Создаем список адресов для обработки
            addresses = [dev.adress for dev in unprocessed_devs]
            
            # Обрабатываем все адреса одновременно используя ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=100) as executor:
                # Запускаем все задачи одновременно
                future_to_address = {
                    executor.submit(process_dev_async, addr): addr 
                    for addr in addresses
                }
                
                # Обрабатываем результаты по мере завершения
                for future in future_to_address:
                    try:
                        result = future.result(timeout=300)  # 5 минут таймаут на один адрес
                        address = future_to_address[future]
                        if result:
                            print(f"Адрес {address} успешно обработан")
                        else:
                            print(f"Адрес {address} не удалось обработать")
                    except Exception as e:
                        address = future_to_address[future]
                        print(f"Ошибка при обработке адреса {address}: {e}")
            
            time.sleep(10)
            
        except KeyboardInterrupt:
            print("Получен сигнал остановки. Завершаем работу...")
            break
        except Exception as e:
            print(f"Критическая ошибка в основном цикле: {e}")
            print("Ждем 60 секунд перед повторной попыткой...")
            time.sleep(60)

if __name__ == "__main__":
    main()

