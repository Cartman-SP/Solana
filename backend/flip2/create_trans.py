from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
from solders.transaction import Transaction
from solders.message import Message
from solders.hash import Hash
from solana.rpc.async_api import AsyncClient
import asyncio
import base64
import requests
import json
import hashlib

# Константы
SYSTEM_PROGRAM_ID = Pubkey.from_string("11111111111111111111111111111111")
PUMP_FUN_PROGRAM_ID = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ASSOCIATED_TOKEN_PROGRAM_ID = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
METADATA_PROGRAM_ID = Pubkey.from_string("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")

# Ваши данные
PRIVATE_KEY = "ovDwkA2VFBHhgX9e9SkFghFjdaFiaDXtyXuTTrwKSA3UDiGsEvPtmhcvoQSxqtUYLSXVqMQQBri4dzpMoz56LUa"
RPC_URL = "https://wispy-little-river.solana-mainnet.quiknode.pro/134b4b837e97bb3711c20296010e32eff69ad1af/"

def get_associated_token_address(wallet_address: Pubkey, token_mint_address: Pubkey) -> Pubkey:
    """Вычисляем адрес ассоциированного токен-аккаунта"""
    return Pubkey.find_program_address(
        [
            bytes(wallet_address),
            bytes(TOKEN_PROGRAM_ID),
            bytes(token_mint_address),
        ],
        ASSOCIATED_TOKEN_PROGRAM_ID
    )[0]

def get_metadata_account(mint_address: Pubkey) -> Pubkey:
    """Вычисляем адрес аккаунта метаданных для токена"""
    return Pubkey.find_program_address(
        [
            b"metadata",
            bytes(METADATA_PROGRAM_ID),
            bytes(mint_address)
        ],
        METADATA_PROGRAM_ID
    )[0]

def get_bonding_curve_pda(token_mint: Pubkey) -> Pubkey:
    """Вычисляем bonding curve PDA"""
    bonding_curve_seed = [b"bonding_curve", bytes(token_mint)]
    bonding_curve_pda, _ = Pubkey.find_program_address(bonding_curve_seed, PUMP_FUN_PROGRAM_ID)
    return bonding_curve_pda

async def check_token_state(token_mint_address: str):
    """Проверяем состояние токена"""
    client = AsyncClient(RPC_URL)
    token_mint = Pubkey.from_string(token_mint_address)
    
    try:
        # Проверяем, существует ли токен
        account_info = await client.get_account_info(token_mint)
        if account_info.value is None:
            print("❌ Токен не существует")
            return False
        
        # Проверяем, не мигрировал ли токен уже в Raydium
        bonding_curve_pda = get_bonding_curve_pda(token_mint)
        bonding_curve_info = await client.get_account_info(bonding_curve_pda)
        
        if bonding_curve_info.value is None:
            print("❌ Токен уже мигрировал в Raydium или не существует на pump.fun")
            return False
        
        print("✅ Токен доступен для покупки на pump.fun")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при проверке состояния токена: {e}")
        return False

async def create_pumpfun_buy_transaction(token_mint_address: str, amount_lamports: int):
    # 1. Подготавливаем ключи
    payer = Keypair.from_base58_string(PRIVATE_KEY)
    token_mint = Pubkey.from_string(token_mint_address)
    client = AsyncClient(RPC_URL)

    # 2. Проверяем состояние токена
    if not await check_token_state(token_mint_address):
        return None

    # 3. Вычисляем необходимые PDA
    bonding_curve_pda = get_bonding_curve_pda(token_mint)
    user_ata = get_associated_token_address(payer.pubkey(), token_mint)
    metadata_account = get_metadata_account(token_mint)

    # 4. Получаем последний blockhash
    recent_blockhash_resp = await client.get_latest_blockhash()
    recent_blockhash = recent_blockhash_resp.value.blockhash

    # 5. Создаем инструкцию покупки с правильным порядком аккаунтов
    # Порядок аккаунтов КРИТИЧЕСКИ важен для pump.fun!
    accounts = [
        AccountMeta(payer.pubkey(), is_signer=True, is_writable=True),  # 0. Payer
        AccountMeta(bonding_curve_pda, is_signer=False, is_writable=True),  # 1. Bonding Curve
        AccountMeta(token_mint, is_signer=False, is_writable=True),  # 2. Token Mint
        AccountMeta(user_ata, is_signer=False, is_writable=True),  # 3. User ATA
        AccountMeta(SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),  # 4. System Program
        AccountMeta(TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),  # 5. Token Program
        AccountMeta(ASSOCIATED_TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),  # 6. Associated Token Program
        AccountMeta(metadata_account, is_signer=False, is_writable=False),  # 7. Metadata Account
    ]

    # 6. Создаем данные инструкции
    # Формат: [дискриминатор инструкции] + [amount (u64 little endian)]
    # Дискриминатор для инструкции "buy" в pump.fun
    discriminator = hashlib.sha256(b"global:buy").digest()[:8]
    data = discriminator + amount_lamports.to_bytes(8, 'little')

    buy_instruction = Instruction(
        program_id=PUMP_FUN_PROGRAM_ID,
        data=data,
        accounts=accounts
    )

    # 7. Создаем сообщение с инструкцией покупки
    message = Message.new_with_blockhash(
        [buy_instruction],
        payer.pubkey(),
        Hash.from_string(str(recent_blockhash))
    )

    # 8. Создаем и подписываем транзакцию
    transaction = Transaction.new_unsigned(message)
    transaction.sign([payer], Hash.from_string(str(recent_blockhash)))

    return transaction

def simulate_bundle(transaction):
    """Функция для симуляции бандла"""
    serialized_tx = base64.b64encode(bytes(transaction)).decode('utf-8')
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "simulateBundle",
        "params": [{
            "encodedTransactions": [serialized_tx],
            "options": {
                "skipPreflight": False,
                "maxSupportedTransactionVersion": 0
            }
        }]
    }
    
    try:
        response = requests.post(RPC_URL, json=payload, timeout=30)
        result = response.json()
        return result
    except Exception as e:
        print(f"Ошибка при симуляции бандла: {e}")
        return None

async def main():
    try:
        # Тестовый токен - замените на актуальный
        token_address = "7QPDEZri9JNJAgNg3D2EGqrNPwBCzk9DeadfUxUMpump"  
        buy_amount = 100000000  # 0.1 SOL в lamports
        
        print("Создаю транзакцию для покупки на pump.fun...")
        transaction = await create_pumpfun_buy_transaction(token_address, buy_amount)
        
        if transaction is None:
            print("❌ Не удалось создать транзакцию")
            return
        
        print("✅ Транзакция создана успешно!")
        print(f"Количество инструкций: {len(transaction.message.instructions)}")
        print(f"Есть подпись: {len(transaction.signatures) > 0}")
        
        # Симулируем бандл
        print("Симулирую бандл...")
        result = simulate_bundle(transaction)
        
        if result and 'result' in result:
            print(f"Результат симуляции: {json.dumps(result, indent=2)}")
            
            # Анализируем результат
            if 'error' in result:
                print(f"❌ Ошибка при симуляции: {result['error']}")
            elif result['result']['value']['summary'].get('failed'):
                print("❌ Транзакция не прошла симуляцию")
                print(f"Ошибка: {result['result']['value']['summary']['failed']}")
                
                # Анализируем конкретную ошибку 0x66
                if 'custom program error: 0x66' in str(result['result']['value']['summary']['failed']):
                    print("\n🔍 Анализ ошибки 0x66:")
                    print("Эта ошибка может быть вызвана одной из следующих причин:")
                    print("1. Токен уже мигрировал в Raydium")
                    print("2. Недостаточный баланс для покупки")
                    print("3. Токен не существует или был удален")
                    print("4. Проблема с состоянием bonding curve")
                    print("5. Изменения в программе pump.fun")
            else:
                print("✅ Симуляция успешна! Транзакция должна работать.")
        else:
            print("❌ Ошибка при симуляции бандла")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())