import requests
import time
import random
import asyncio
import os
import json
import ast

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjcmVhdGVkQXQiOjE3NTM1NzAxNzU2MjEsImVtYWlsIjoiZGFuaWlsLnNoaXJraW4wMDVAZ21haWwuY29tIiwiYWN0aW9uIjoidG9rZW4tYXBpIiwiYXBpVmVyc2lvbiI6InYyIiwiaWF0IjoxNzUzNTcwMTc1fQ.W2-ic8rt8wQZptdygjc6F3Z5N8CJv1UrCkfqzdwq2vw"



def make_api_request(url, headers, max_retries=10):
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:  # Rate limit exceeded
                print(f"Rate limit exceeded. Попытка {attempt + 1}/{max_retries}")
                time.sleep(10)
                continue
            else:
                print(f"API ошибка {response.status_code}: {response.text}")
                
        except requests.exceptions.RequestException as e:
            time.sleep(random.uniform(1, 3))
            continue
        except Exception as e:
            time.sleep(random.uniform(1, 3))
            continue
    
    return None

async def get_funding_addresses(wallet_address):
    base_url = "https://pro-api.solscan.io/v2.0/account/metadata"
    
    headers = {
        "token": API_KEY,
        "User-Agent": "SolanaFlipper/1.0"
    }
    
    # Формируем URL для входящих трансферов (flow=in), чтобы получить только фондирующие адреса
    url = f"{base_url}?address={wallet_address}"
    
    try:
        data = await asyncio.to_thread(make_api_request, url, headers)
        if not data:
            return {}
        data = data.get('data', {}).get('funded_by', {}).get('funded_by', '')
        return data
    except Exception as e:
        print(f"Error: {e}")
        return {}



async def _fetch_with_semaphore(semaphore, wallet_address):
    async with semaphore:
        faund_address = await get_funding_addresses(wallet_address)
        return {"main": wallet_address, "faund": faund_address}


async def build_faunds_json(concurrency: int = 5):
    # Определяем пути
    root_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../"))
    devs_path = os.path.join(root_dir, "devs.txt")
    output_path = os.path.join(root_dir, "faunds.json")

    # Читаем адреса из devs.txt (формат: Python list)
    with open(devs_path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    addresses = ast.literal_eval(content) if content else []

    # Асинхронно получаем данные с ограничением параллелизма
    semaphore = asyncio.Semaphore(max(1, concurrency))
    tasks = [asyncio.create_task(_fetch_with_semaphore(semaphore, addr)) for addr in addresses]
    results = await asyncio.gather(*tasks)

    # Пишем в JSON
    payload = {"data": results}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    asyncio.run(build_faunds_json())
