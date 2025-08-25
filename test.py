import requests
import json

# URL Solana API
url = "https://api.mainnet-beta.solana.com"

# Заголовки запроса
headers = {
    "Content-Type": "application/json"
}

# Тело запроса
payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "getTransaction",
    "params": [
        "27SuJ12J9CgRocTZNTKAwL2KwccWezJfGpPWYrqk5YB12uZsY5tzkLB4Dx8Fv193k9FUngSg5Z2tcz6Cx3FLKoXC",
        {
            "encoding": "jsonParsed",
            "maxSupportedTransactionVersion": 0
        }
    ]
}

try:
    # Отправка POST запроса
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()  # Проверка на ошибки HTTP
    
    # Парсинг JSON ответа
    result = response.json()
    
    # Красивое форматирование вывода (аналогично jq)
    print(json.dumps(result, indent=2))
    
except requests.exceptions.RequestException as e:
    print(f"Ошибка запроса: {e}")
except json.JSONDecodeError as e:
    print(f"Ошибка парсинга JSON: {e}")