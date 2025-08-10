import requests
import time
api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjcmVhdGVkQXQiOjE3NTM1NzAxNzU2MjEsImVtYWlsIjoiZGFuaWlsLnNoaXJraW4wMDVAZ21haWwuY29tIiwiYWN0aW9uIjoidG9rZW4tYXBpIiwiYXBpVmVyc2lvbiI6InYyIiwiaWF0IjoxNzUzNTcwMTc1fQ.W2-ic8rt8wQZptdygjc6F3Z5N8CJv1UrCkfqzdwq2vw"


def get_funding_addresses(wallet_address):
    base_url = "https://pro-api.solscan.io/v2.0/account/metadata"
    
    headers = {
        "token": api_key,
        "User-Agent": "SolanaFlipper/1.0"
    }
    
    # Формируем URL для входящих трансферов (flow=in), чтобы получить только фондирующие адреса
    url = f"{base_url}?address={wallet_address}"
    
    try:
        data = requests.get(url = url, headers=headers).json()
        data = data.get('data', [])
        return data
    except Exception as e:
        print(f"Error: {e}")
        return []



limit = 15
def search_wallet(address):
    counter = 0
    accounts = []
    while counter < limit:
        data = get_funding_addresses(address)
        address = data['funded_by']['funded_by']
        for i in accounts:
            if address in i['funded_by']['funded_by']:
                return accounts  
        accounts.append(data)
        counter += 1
    
    return accounts    

print(search_wallet("GrA6H8KqbFdeHzDsoYoZUrjXhpNKuxCRrGNpZ2Em6kC"))