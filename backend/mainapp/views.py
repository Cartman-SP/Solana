from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from .models import UserDev
from django.views.decorators.http import require_http_methods
import os
from datetime import datetime
import base58
import struct
import base64

LOCAL_WS_URL = "ws://localhost:9393"


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def blacklist_user(request):
    """API эндпоинт для добавления пользователя в blacklist по адресу токена"""
    
    # Обработка CORS preflight запроса
    if request.method == "OPTIONS":
        response = JsonResponse({})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type"
        return response
    
    try:
        data = json.loads(request.body)
        token_address = data.get('token_address')
        
        if not token_address:
            response = JsonResponse({
                'success': False,
                'error': 'token_address is required'
            }, status=400)
            response["Access-Control-Allow-Origin"] = "*"
            return response
        
        # Импортируем модель Token
        from .models import Token
        
        # Находим токен и получаем связанного UserDev
        try:
            token = Token.objects.get(address=token_address)
            user_dev = token.dev
            
            if user_dev:
                user_dev.blacklist = True
                user_dev.save()
                
                response = JsonResponse({
                    'success': True,
                    'message': f'User {user_dev.adress} added to blacklist via token {token_address}'
                })
                response["Access-Control-Allow-Origin"] = "*"
                return response
            else:
                response = JsonResponse({
                    'success': False,
                    'error': f'No UserDev found for token {token_address}'
                }, status=404)
                response["Access-Control-Allow-Origin"] = "*"
                return response
                
        except Token.DoesNotExist:
            response = JsonResponse({
                'success': False,
                'error': f'Token {token_address} not found'
            }, status=404)
            response["Access-Control-Allow-Origin"] = "*"
            return response
            
    except json.JSONDecodeError:
        response = JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
        response["Access-Control-Allow-Origin"] = "*"
        return response
    except Exception as e:
        response = JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
        response["Access-Control-Allow-Origin"] = "*"
        return response


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def whitelist_user(request):
    """API эндпоинт для добавления пользователя в whitelist по адресу токена"""
    
    # Обработка CORS preflight запроса
    if request.method == "OPTIONS":
        response = JsonResponse({})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type"
        return response
    
    try:
        data = json.loads(request.body)
        token_address = data.get('token_address')
        
        if not token_address:
            response = JsonResponse({
                'success': False,
                'error': 'token_address is required'
            }, status=400)
            response["Access-Control-Allow-Origin"] = "*"
            return response
        
        # Импортируем модель Token
        from .models import Token
        
        # Находим токен и получаем связанного UserDev
        try:
            token = Token.objects.get(address=token_address)
            user_dev = token.dev
            
            if user_dev:
                user_dev.whitelist = True
                user_dev.save()
                
                response = JsonResponse({
                    'success': True,
                    'message': f'User {user_dev.adress} added to whitelist via token {token_address}'
                })
                response["Access-Control-Allow-Origin"] = "*"
                return response
            else:
                response = JsonResponse({
                    'success': False,
                    'error': f'No UserDev found for token {token_address}'
                }, status=404)
                response["Access-Control-Allow-Origin"] = "*"
                return response
                
        except Token.DoesNotExist:
            response = JsonResponse({
                'success': False,
                'error': f'Token {token_address} not found'
            }, status=404)
            response["Access-Control-Allow-Origin"] = "*"
            return response
            
    except json.JSONDecodeError:
        response = JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
        response["Access-Control-Allow-Origin"] = "*"
        return response
    except Exception as e:
        response = JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
        response["Access-Control-Allow-Origin"] = "*"
        return response






def parse_create_instruction(program_data: str) -> dict:
    """Парсит данные инструкции Create из Pump.fun"""
    try:
        decoded_data = base64.b64decode(program_data)
        offset = 0
        
        # Парсим discriminator (первые 8 байт)
        discriminator = decoded_data[offset:offset + 8].hex()
        offset += 8
        
        # Парсим имя токена
        name_len = struct.unpack_from('<I', decoded_data, offset)[0]
        offset += 4
        name = decoded_data[offset:offset + name_len].decode('utf-8').rstrip('\x00')
        offset += name_len
        
        # Парсим символ токена
        symbol_len = struct.unpack_from('<I', decoded_data, offset)[0]
        offset += 4
        symbol = decoded_data[offset:offset + symbol_len].decode('utf-8').rstrip('\x00')
        offset += symbol_len
        
        # Парсим URI токена
        uri_len = struct.unpack_from('<I', decoded_data, offset)[0]
        offset += 4
        uri = decoded_data[offset:offset + uri_len].decode('utf-8').rstrip('\x00')
        offset += uri_len
        
        # Парсим mint account (32 байта)
        mint_bytes = decoded_data[offset:offset + 32]
        mint = base58.b58encode(mint_bytes).decode('utf-8')
        offset += 32
        
        # Пропускаем 32 байта (похоже на bonding curve)
        bonding_curve_bytes = decoded_data[offset:offset + 32]
        offset += 32
        
        # Пропускаем еще 32 байта
        associated_bonding_curve_bytes = decoded_data[offset:offset + 32]
        offset += 32
        
        # Парсим user account (32 байта)
        user_bytes = decoded_data[offset:offset + 32]
        user = base58.b58encode(user_bytes).decode('utf-8')
        offset += 32
        
        # Остальные данные (если есть)
        remaining_data = decoded_data[offset:]
        
        parsed_data = {
            "source": "bonk",
            "mint": mint,
            "user": user,
            "name": name,
            "symbol": symbol,
            "uri": uri,
        }
        
        return parsed_data
    except:
        return None


def send_to_local_websocket(data: dict):
    """Отправляет данные в локальный WebSocket"""
    try:
        # Синхронная версия - просто логируем данные
        print(f"WebSocket data: {json.dumps(data, indent=2)}")
    except:
        pass


def write_to_programs_file(program_data: str, parsed_data: dict):
    """Записывает program_data и parsed_data в файл programs.txt"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'programs.txt')
        
        log_entry = f"\n{'='*50}\n"
        log_entry += f"Timestamp: {timestamp}\n"
        log_entry += f"Program Data:\n{program_data}\n"
        log_entry += f"Parsed Data:\n{json.dumps(parsed_data, indent=2, ensure_ascii=False)}\n"
        log_entry += f"{'='*50}\n"
        
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Error writing to programs.txt: {e}")


def process_logs(logs: list):
    """Обрабатывает логи и извлекает данные Create инструкции"""
    has_create_instruction = False
    program_data = None
    for log in logs:
        if "Program log: Instruction: InitializeMint" in log:
            has_create_instruction = True
        elif 'Program data: ' in log:
            program_data = log.split('Program data: ')[1].strip()
            break
    
    print(program_data)
    if has_create_instruction and program_data:
        parsed_data = parse_create_instruction(program_data)
        if parsed_data:
            send_to_local_websocket(parsed_data)
            
            # Записываем данные в файл programs.txt


def write_to_webhooks_file(webhook_data):
    """Записывает весь вебхук в файл webhooks.txt"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'webhooks.txt')
        
        log_entry = f"\n{'='*50}\n"
        log_entry += f"Timestamp: {timestamp}\n"
        log_entry += f"Webhook Data:\n{json.dumps(webhook_data, indent=2, ensure_ascii=False)}\n"
        log_entry += f"{'='*50}\n"
        
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Error writing to webhooks.txt: {e}")


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def bonk_webhook(request):
    """API эндпоинт для приема вебхуков и записи данных о токене в файл webhooks.txt"""
    
    # Обработка CORS preflight запроса
    if request.method == "OPTIONS":
        response = JsonResponse({})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type"
        return response
    
    try:
        # Получаем содержимое запроса
        if request.content_type == 'application/json':
            webhook_data = json.loads(request.body)
        else:
            webhook_data = json.loads(request.body.decode('utf-8', errors='ignore'))
        
        # Записываем весь вебхук в файл
        write_to_webhooks_file(webhook_data)
        
        # Создаем временную метку
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Извлекаем данные о токене
        token_data = {}
        
        # Обрабатываем массив транзакций
        if isinstance(webhook_data, list):
            for tx in webhook_data:
                if 'meta' in tx and 'logMessages' in tx['meta']:
                    log_messages = tx['meta']['logMessages']
                    process_logs(log_messages)
        elif isinstance(webhook_data, dict) and 'meta' in webhook_data and 'logMessages' in webhook_data['meta']:
            log_messages = webhook_data['meta']['logMessages']
            process_logs(log_messages)
        
        response = JsonResponse({
            'success': True,
            'message': 'Webhook processed and logged successfully',
            'timestamp': timestamp,
            'token_data': token_data
        })
        response["Access-Control-Allow-Origin"] = "*"
        return response
        
    except Exception as e:
        response = JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
        response["Access-Control-Allow-Origin"] = "*"
        return response
import requests
import time

api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjcmVhdGVkQXQiOjE3NTM1NzAxNzU2MjEsImVtYWlsIjoiZGFuaWlsLnNoaXJraW4wMDVAZ21haWwuY29tIiwiYWN0aW9uIjoidG9rZW4tYXBpIiwiYXBpVmVyc2lvbiI6InYyIiwiaWF0IjoxNzUzNTcwMTc1fQ.W2-ic8rt8wQZptdygjc6F3Z5N8CJv1UrCkfqzdwq2vw"


def get_funding_addresses(wallet_address):
    base_url = "https://pro-api.solscan.io/v2.0/account/metadata"
    
    headers = {
        "token": api_key,
        "User-Agent": "SolanaFlipper/1.0"
    }
    
    url = f"{base_url}?address={wallet_address}"
    print(f"Requesting URL: {url}")
    
    try:
        response = requests.get(url=url, headers=headers)
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response data: {data}")
            result = data.get('data', {})
            print(f"Returning: {result} (type: {type(result)})")
            return result
        else:
            print(f"Bad status code: {response.status_code}")
            return {}
    except Exception as e:
        print(f"Error in get_funding_addresses: {e}")
        return {}



limit = 15
def search_wallet(address):
    counter = 0
    accounts = []
    print(f"Starting search_wallet for address: {address}")
    
    while counter < limit:
        data = get_funding_addresses(address)
        print(f"Counter: {counter}, Data type: {type(data)}, Data: {data}")
        
        # Проверяем, что data не пустой и является словарем
        if not data or not isinstance(data, dict):
            print(f"Returning accounts (empty or not dict): {accounts}")
            return accounts
            
        try:
            # Проверяем существование ключей перед обращением
            if 'funded_by' in data and 'funded_by' in data['funded_by']:
                address = data['funded_by']['funded_by']
                print(f"New address: {address}")
            else:
                print(f"No funded_by keys found, returning accounts: {accounts}")
                return accounts
        except (KeyError, TypeError) as e:
            print(f"Exception in search_wallet: {e}")
            return accounts
            
        # Проверяем дубликаты
        for i in accounts:
            if isinstance(i, dict) and 'funded_by' in i and 'funded_by' in i['funded_by']:
                if address in i['funded_by']['funded_by']:
                    print(f"Duplicate found, returning accounts: {accounts}")
                    return accounts  
        accounts.append(data)
        counter += 1
    
    print(f"Limit reached, returning accounts: {accounts}")
    return accounts    

@csrf_exempt
def get_wallets(request):
    try:
        # Поддерживаем как GET, так и POST запросы
        if request.method == "GET":
            token_address = request.GET.get('token_address')
        else:
            data = json.loads(request.body)
            token_address = data.get('token_address')
        
        if not token_address:
            return JsonResponse({"success": False, "error": "token_address is required"})
            
        result = search_wallet(token_address)
        
        # Проверяем, что result является списком или словарем
        if not isinstance(result, (list, dict)):
            result = []
            
        return JsonResponse({"data": result})
    except Exception as e:
        print(f"Error in get_wallets: {e}")
        return JsonResponse({"success": False, "error": str(e)})