# pip install requests
import requests, base64

# Ваш RPC-URL (с "длинным секретом" в пути)
RPC_URL = "https://wispy-little-river.solana-mainnet.quiknode.pro/134b4b837e97bb3711c20296010e32eff69ad1af/"

# Сюда вставьте строку base64 транзакции БЕЗ лишних кавычек/переводов строк
TX_BASE64 = "4hXTCkRzt9WyecNzV1XPgCDfGAZzQKNxLXgynz5QDuWWPSAZBZSHptvWRL3BjCvzUXRdKvHL2b7yGrRQcWyaqsaBCncVG7BFggS8w9snUts67BSh3EqKpXLUm5UMHfD7ZBe9GhARjbNQMLJ1QD3Spr6oMTBU6EhdB4RD8CP2xUxr2u3d6fos36PD98XS6oX8TQjLpsMwncs5DAMiD4nNnR8NBfyghGCWvCVifVwvA8B8TJxE1aiyiv2L429BCWfyzAme5sZW8rDb14NeCQHhZbtNqfXhcp2tAnaAT"

def buy(method):
    # (Опционально) проверим, что base64 корректный
    try:
        base64.b64decode(TX_BASE64, validate=True)
    except Exception as e:
        raise ValueError(f"Некорректная base64-строка транзакции: {e}")

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "sendTransaction",  # "sendRawTransaction" (рекомендуется) или "sendTransaction"
        "params": [
            TX_BASE64,
            {
                # на снайпе обычно ускоряемся:
                "skipPreflight": True,
                "preflightCommitment": "processed",
                "maxRetries": 5
            }
        ],
    }

    r = requests.post(RPC_URL, json=payload, timeout=15)
    r.raise_for_status()
    resp = r.json()

    if "error" in resp:
        raise RuntimeError(f"RPC error: {resp['error']}")
    return resp["result"]  # подпись (signature)

if __name__ == "__main__":
