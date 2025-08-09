import requests
import json

# Конфигурация
HELIUS_API_KEY = "d25e743a-6bf4-4ff2-a939-08767d664564"
WEBHOOK_URL = "https://goodelivery.ru/api/bonk/"
PROGRAM_ADDRESS = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

# URL API Helius
BASE_URL = f"https://api.helius.xyz/v0/webhooks?api-key={HELIUS_API_KEY}"

def delete_existing_webhooks():
    try:
        # Получаем список всех вебхуков
        response = requests.get(BASE_URL)
        
        if response.status_code == 200:
            webhooks = response.json()
            for webhook in webhooks:
                if webhook['webhookURL'] == WEBHOOK_URL:
                    # Удаляем найденный вебхук
                    delete_url = f"https://api.helius.xyz/v0/webhooks/{webhook['id']}?api-key={HELIUS_API_KEY}"
                    del_response = requests.delete(delete_url)
                    if del_response.status_code == 200:
                        print(f"Вебхук {webhook['id']} успешно удален")
                    else:
                        print(f"Ошибка при удалении вебхука {webhook['id']}")
        else:
            print("Не удалось получить список вебхуков")
    except Exception as e:
        print("Ошибка при удалении вебхуков:", str(e))

def create_enhanced_webhook():
    webhook_data = {
        "webhookURL": WEBHOOK_URL,
        "transactionTypes": ["TokenMint"],
        "accountAddresses": [PROGRAM_ADDRESS],
        "webhookType": "enhanced",
        "authHeader": None,  # Добавьте, если требуется
    }

    try:
        response = requests.post(
            BASE_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(webhook_data)
        )
        
        if response.status_code == 200:
            print("Enhanced вебхук для TokenMint успешно создан!")
            print("Детали:", response.json())
        else:
            print("Ошибка при создании вебхука:")
            print("Код статуса:", response.status_code)
            print("Ответ:", response.text)
    except Exception as e:
        print("Произошла ошибка:", str(e))

if __name__ == "__main__":
    print("Удаляю существующие вебхуки...")
    delete_existing_webhooks()
    
    print("\nСоздаю новый enhanced вебхук для TokenMint...")
    create_enhanced_webhook()