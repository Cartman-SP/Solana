import aiohttp
import time

async def make_api_request(session: aiohttp.ClientSession, url: str, headers: dict) -> dict:
    async with session.get(url, headers=headers) as response:
        if response.status != 200:
            raise Exception(f"API request failed with status {response.status}: {await response.text()}")
        return await response.json()

async def get_funding_addresses(session: aiohttp.ClientSession, wallet_address: str, api_key: str, page_size: int = 100) -> list[str]:
    base_url = "https://pro-api.solscan.io/v2.0/account/metadata"
    
    headers = {
        "token": api_key,
        "User-Agent": "SolanaFlipper/1.0"
    }
    
    # Формируем URL для входящих трансферов (flow=in), чтобы получить только фондирующие адреса
    url = f"{base_url}?address={wallet_address}"
    
    try:
        data = await make_api_request(session, url, headers)
        data = data.get('data', [])
        print(data)
        adress = data.get('funded_by', []).get('funded_by', []) 
        return adress
    except Exception as e:
        print(f"Error: {e}")
        return []

async def main():
    start_time = time.time()  # Засекаем время начала
    print(f"Начинаем работу в {time.strftime('%H:%M:%S')}")
    
    API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjcmVhdGVkQXQiOjE3NTM1NzAxNzU2MjEsImVtYWlsIjoiZGFuaWlsLnNoaXJraW4wMDVAZ21haWwuY29tIiwiYWN0aW9uIjoidG9rZW4tYXBpIiwiYXBpVmVyc2lvbiI6InYyIiwiaWF0IjoxNzUzNTcwMTc1fQ.W2-ic8rt8wQZptdygjc6F3Z5N8CJv1UrCkfqzdwq2vw"
    
    async with aiohttp.ClientSession() as session:
        funding = "FaLrsX8KZG8DBhCD4trbH3KdZN2p2SbkpnNaZXtFh7dw"
        prev_funding = None
        while not(funding in ["2ojv9BAiHUrvsm9gxDe7fJSzbNZSJcxZvf8dqmWGHG8S","BmFdpraQhkiDQE6SnfG5omcA1VwzqfXrwtNYBwWTymy6","FWznbcNXWQuHTawe9RxvQ2LdCENssh12dsznf4RiouN5"]):
            prev_funding = funding
            funding = await get_funding_addresses(session,funding, API_KEY)
        
        end_time = time.time()  # Засекаем время окончания
        execution_time = end_time - start_time  # Вычисляем время выполнения
        
        print(f"Результат: {prev_funding}")
        print(f"Время выполнения: {execution_time:.2f} секунд")
        print(f"Завершено в {time.strftime('%H:%M:%S')}")
if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
