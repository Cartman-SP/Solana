import django
import sys
import os
import requests
import asyncio
import time
import uuid
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
import random
import threading
from collections import deque
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import UserDev, AdminDev
from asgiref.sync import sync_to_async
from django.db import IntegrityError

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjcmVhdGVkQXQiOjE3NTM1NzAxNzU2MjEsImVtYWlsIjoiZGFuaWlsLnNoaXJraW4wMDVAZ21haWwuY29tIiwiYWN0aW9uIjoidG9rZW4tYXBpIiwiYXBpVmVyc2lvbiI6InYyIiwiaWF0IjoxNzUzNTcwMTc1fQ.W2-ic8rt8wQZptdygjc6F3Z5N8CJv1UrCkfqzdwq2vw"

MAX_REQUESTS_PER_MINUTE = 1000

# Потокобезопасный лимитер (скользящее окно 60с)
_rate_lock = threading.Lock()
_request_times = deque()

def acquire_rate_limit_slot():
    """Блокирует до тех пор, пока не освободится слот в лимите RPS/RPM."""
    while True:
        now = time.time()
        with _rate_lock:
            # Очистка старых таймстампов
            while _request_times and (now - _request_times[0]) >= 60:
                _request_times.popleft()
            if len(_request_times) < MAX_REQUESTS_PER_MINUTE:
                _request_times.append(now)
                return
            # Время ожидания до освобождения старейшей записи
            wait_time = max(0.0, 60 - (now - _request_times[0]))
        # Спим небольшими порциями, чтобы быстрее реагировать
        time.sleep(min(wait_time, 1.0))

# Пул HTTP-соединений на потоках
_thread_local = threading.local()

def get_session() -> requests.Session:
    if not hasattr(_thread_local, "session"):
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=200, max_retries=0)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update({"User-Agent": "SolanaFlipper/1.0"})
        _thread_local.session = session
    return _thread_local.session

def make_api_request(url, headers, max_retries=3):
    """Выполняет API запрос с обработкой ошибок и перезапусками"""
    for attempt in range(max_retries):
        try:
            acquire_rate_limit_slot()
            session = get_session()
            response = session.get(url, headers=headers, timeout=(5, 30))
            
            if response.status_code == 200:
                try:
                    return response.json()
                except Exception:
                    return None
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


_cache_lock = threading.Lock()
_funding_cache = {}
_birzh_cache = {}
CACHE_TTL_FUNDING = 600  # 10 минут
CACHE_TTL_BIRZH = 1800   # 30 минут

def _cache_get(cache_obj, key, ttl):
    now = time.time()
    with _cache_lock:
        item = cache_obj.get(key)
        if not item:
            return None
        ts, value = item
        if (now - ts) <= ttl:
            return value
        # просрочено
        cache_obj.pop(key, None)
        return None

def _cache_set(cache_obj, key, value, max_size=50000):
    with _cache_lock:
        cache_obj[key] = (time.time(), value)
        if len(cache_obj) > max_size:
            # Простая усечка: удалим ~1k первых ключей
            for _ in range(1000):
                try:
                    cache_obj.pop(next(iter(cache_obj)))
                except StopIteration:
                    break

def check_birzh(address, tags):
    cached = _cache_get(_birzh_cache, address, CACHE_TTL_BIRZH)
    if cached is not None:
        return cached
    if "exchange_wallet" in tags or "deposit_address" in tags:
        _cache_set(_birzh_cache, address, True)
        return True
    
    base_url = "https://pro-api.solscan.io/v2.0/account/"
    url = f"{base_url}transfer?address={address}&activity_type[]=ACTIVITY_SPL_TRANSFER&page=1&page_size=100&sort_by=block_time&sort_order=desc"    
    headers = {"token": API_KEY}
    
    response = make_api_request(url, headers)
    if response is None:
        _cache_set(_birzh_cache, address, False)
        return False
    
    data = response.get('data', [])
    if not data:
        _cache_set(_birzh_cache, address, False)
        return False
    
    try:
        ago = minutes_since(data[10]['time'])
    except:
        ago = minutes_since(data[-1]['time'])

    if ago < 6 and len(data) == 100:
        _cache_set(_birzh_cache, address, True)
        return True

    url = f"{base_url}portfolio?address={address}&exclude_low_score_tokens=true"    
    response = make_api_request(url, headers)
    if response is None:
        _cache_set(_birzh_cache, address, False)
        return False
    
    data = response.get('data', [])
    try:
        balance = data.get("total_value", {})
    except:
        balance = 0
    
    if balance > 30000:
        _cache_set(_birzh_cache, address, True)
        return True
    _cache_set(_birzh_cache, address, False)
    return False

def get_funding_addresses(wallet_address):
    cached = _cache_get(_funding_cache, wallet_address, CACHE_TTL_FUNDING)
    if cached is not None:
        return cached
    base_url = "https://pro-api.solscan.io/v2.0/account/metadata"
    
    headers = {
        "token": API_KEY,
        "User-Agent": "SolanaFlipper/1.0"
    }
    
    # Формируем URL для входящих трансферов (flow=in), чтобы получить только фондирующие адреса
    url = f"{base_url}?address={wallet_address}"
    
    data = make_api_request(url, headers)
    if data is None:
        _cache_set(_funding_cache, wallet_address, {})
        return {}
    
    data = data.get('data', {})
    _cache_set(_funding_cache, wallet_address, data)
    return data


def create_admin_with_unique_twitter():
    """Создает AdminDev с уникальным twitter, перегенерируя при коллизии."""
    while True:
        unique_twitter = f"admin_{uuid.uuid4().hex[:8]}"
        if not AdminDev.objects.filter(twitter=unique_twitter).exists():
            try:
                return AdminDev.objects.create(twitter=unique_twitter)
            except IntegrityError:
                # Возможная гонка при параллельном создании
                continue

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
            admin = create_admin_with_unique_twitter()
            return arr, admin
        dev, created = UserDev.objects.get_or_create(
            adress=fund,
        )
        dev.faunded = True
        # Быстрый апдейт только нужного поля, чтобы уменьшить накладные расходы
        try:
            UserDev.objects.filter(pk=dev.pk).update(faunded=True)
        except Exception:
            # На всякий случай откат к обычному save
            dev.save(update_fields=["faunded"])
        if created:
            arr.append(dev)
            count += 1
        else:
            if dev.admin:
                arr.append(dev)
                return arr, dev.admin
            else:
                admin = create_admin_with_unique_twitter()
                arr.append(dev)
                return arr, admin
    admin = create_admin_with_unique_twitter()
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
        
        total_tokens = 0
        # Подготовим массовое обновление
        for i in range(len(arr)):
            obj = arr[i]
            total_tokens += obj.total_tokens
            obj.admin = admin
            obj.faunded = True
            try:
                obj.faunded_by = arr[i+1]
            except Exception:
                pass
        try:
            UserDev.objects.bulk_update(arr, ["admin", "faunded", "faunded_by"])
        except Exception:
            # Fallback на поштучные сохранения, если bulk_update невозможен
            for obj in arr:
                try:
                    obj.save(update_fields=["admin", "faunded", "faunded_by"])
                except Exception:
                    obj.save()
        
        admin.total_tokens += total_tokens
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
            # Подбираем разумное число потоков, чтобы не упираться в RPM API
            max_workers = max(8, min(32, len(addresses)))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_address = {executor.submit(process_dev_async, addr): addr for addr in addresses}
                for future in as_completed(future_to_address.keys()):
                    address = future_to_address[future]
                    try:
                        result = future.result(timeout=300)  # 5 минут таймаут на один адрес
                        if result:
                            print(f"Адрес {address} успешно обработан")
                        else:
                            print(f"Адрес {address} не удалось обработать")
                    except Exception as e:
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

