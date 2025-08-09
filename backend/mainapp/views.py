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
    except :
        return None


async def send_to_local_websocket(data: dict):
    """Отправляет данные в локальный WebSocket"""
    try:
        async with websockets.connect(LOCAL_WS_URL, timeout=5) as websocket:
            await websocket.send(json.dumps(data))
    except:
        pass


async def process_logs(logs: list):
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
            await send_to_local_websocket(parsed_data)





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
    
        # Получаем содержимое запроса
    if request.content_type == 'application/json':
        webhook_data = json.loads(request.body)
    else:
        webhook_data = json.loads(request.body.decode('utf-8', errors='ignore'))
    
    # Создаем временную метку
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Извлекаем данные о токене
    token_data = {}
    
    # Обрабатываем массив транзакций
    if isinstance(webhook_data, list):
        for tx in webhook_data:
            if 'meta' in tx and 'logMessages' in tx['meta']:
                log_messages = tx['meta']['logMessages']
                process_logs(logs)




    response = JsonResponse({
        'success': True,
        'message': 'Webhook processed and token data logged successfully',
        'timestamp': timestamp,
        'token_data': token_data
    })
    response["Access-Control-Allow-Origin"] = "*"
    return response
        
