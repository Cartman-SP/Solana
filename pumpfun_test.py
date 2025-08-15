import asyncio
import json
import os

import websockets


HELIUS_API_KEY = "5bce1ed6-a93a-4392-bac8-c42190249194"
WS_URL = f"wss://atlas-mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

# Укажите адрес аккаунта для фильтра (можно через переменную окружения HELIUS_ACCOUNT)
ACCOUNT_ADDRESS = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"


def build_subscription_payload(account_address: str) -> dict:
	return {
		"jsonrpc": "2.0",
		"id": 1,
		"method": "transactionSubscribe",
		"params": [
			{
				"accountInclude": [account_address],
				"failed": False,
				"vote": False,
			},
			{
				"commitment": "confirmed",
				"encoding": "jsonParsed",
				"transactionDetails": "full",
				"maxSupportedTransactionVersion": 0,
			},
		],
	}


async def run_subscription() -> None:
	if ACCOUNT_ADDRESS == "YOUR_ACCOUNT_ADDRESS":
		print(
			"[ВНИМАНИЕ] Задайте адрес аккаунта в переменной окружения HELIUS_ACCOUNT "
			"или измените константу ACCOUNT_ADDRESS в pumpfun_test.py"
		)

	payload = build_subscription_payload(ACCOUNT_ADDRESS)
	print(f"Подключение к {WS_URL}")
	async for websocket in websockets.connect(WS_URL):
		try:
			await websocket.send(json.dumps(payload))
			# Первое сообщение — подтверждение подписки (subscription id)
			ack = await websocket.recv()
			print(f"ACK: {ack}")

			# Далее — поток уведомлений
			while True:
				message = await websocket.recv()
				print(message)
		except websockets.exceptions.ConnectionClosedError as e:
			print(f"WebSocket закрыт: {e}. Переподключение...")
			continue
		except Exception as e:
			print(f"Ошибка: {e}. Переподключение через 3с...")
			await asyncio.sleep(3)
			continue


if __name__ == "__main__":
	asyncio.run(run_subscription())


