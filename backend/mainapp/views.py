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

# Create your views here.

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


def extract_token_data_from_logs(log_messages):
    """Извлекает данные токена из logMessages"""
    token_data = {}
    
    try:
        # Ищем строку с "Program data:"
        program_data = None
        for log in log_messages:
            if log.startswith("Program data:"):
                program_data = log.replace("Program data:", "").strip()
                break
        
        if not program_data:
            return token_data
        
        # Декодируем base58 данные
        try:
            data_bytes = base58.b58decode(program_data)
            instruction_data = data_bytes.hex()
        except:
            return token_data
        
        # Преобразуем hex в bytes
        data_bytes = bytes.fromhex(instruction_data)
        
        # Извлекаем данные по структуре из bonk.py
        if len(data_bytes) >= 96:
            # Pool State (32 bytes)
            pool_state_bytes = data_bytes[0:32]
            pool_state = base58.b58encode(pool_state_bytes).decode('utf-8')
            token_data['Pool State'] = pool_state

            # Creator (32 bytes)
            creator_bytes = data_bytes[32:64]
            creator = base58.b58encode(creator_bytes).decode('utf-8')
            token_data['Creator'] = creator

            # Config (32 bytes)
            config_bytes = data_bytes[64:96]
            config = base58.b58encode(config_bytes).decode('utf-8')
            token_data['Config'] = config

            # Curve params (16 bytes) + decimals
            curve_param_size = 16
            decimals_start = 96 + curve_param_size
            
            if len(data_bytes) > decimals_start:
                decimals = data_bytes[decimals_start]
                token_data['Decimals'] = decimals

                # Name
                name_length_start = decimals_start + 1
                if len(data_bytes) >= name_length_start + 4:
                    name_length = struct.unpack('<I', data_bytes[name_length_start:name_length_start + 4])[0]
                    name_start = name_length_start + 4
                    name_end = name_start + name_length
                    
                    if len(data_bytes) >= name_end:
                        name = data_bytes[name_start:name_end].decode('utf-8', errors='ignore')
                        token_data['Token Name'] = name

                        # Symbol
                        symbol_length_start = name_end
                        if len(data_bytes) >= symbol_length_start + 4:
                            symbol_length = struct.unpack('<I', data_bytes[symbol_length_start:symbol_length_start + 4])[0]
                            symbol_start = symbol_length_start + 4
                            symbol_end = symbol_start + symbol_length
                            
                            if len(data_bytes) >= symbol_end:
                                symbol = data_bytes[symbol_start:symbol_end].decode('utf-8', errors='ignore')
                                token_data['Token Symbol'] = symbol

                                # URI
                                uri_length_start = symbol_end
                                if len(data_bytes) >= uri_length_start + 4:
                                    uri_length = struct.unpack('<I', data_bytes[uri_length_start:uri_length_start + 4])[0]
                                    uri_start = uri_length_start + 4
                                    uri_end = uri_start + uri_length
                                    
                                    if len(data_bytes) >= uri_end:
                                        uri = data_bytes[uri_start:uri_end].decode('utf-8', errors='ignore')
                                        token_data['Token URI'] = uri
    
    except Exception as e:
        print(f"Error extracting token data: {e}")
    
    return token_data


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
        
        # Создаем временную метку
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Извлекаем данные о токене
        token_data = {}
        
        # Обрабатываем массив транзакций
        if isinstance(webhook_data, list):
            for tx in webhook_data:
                if 'meta' in tx and 'logMessages' in tx['meta']:
                    log_messages = tx['meta']['logMessages']
                    tx_token_data = extract_token_data_from_logs(log_messages)
                    if tx_token_data:
                        token_data.update(tx_token_data)
                        break  # Берем данные из первой транзакции с данными токена
        elif isinstance(webhook_data, dict) and 'meta' in webhook_data and 'logMessages' in webhook_data['meta']:
            log_messages = webhook_data['meta']['logMessages']
            token_data = extract_token_data_from_logs(log_messages)
        
        # Формируем запись для файла
        if token_data:
            log_entry = f"\n{'='*50}\n"
            log_entry += f"Timestamp: {timestamp}\n"
            log_entry += f"Token Data:\n"
            for key, value in token_data.items():
                log_entry += f"  {key}: {value}\n"
            log_entry += f"{'='*50}\n"
        else:
            log_entry = f"\n{'='*50}\n"
            log_entry += f"Timestamp: {timestamp}\n"
            log_entry += f"No token data found in webhook\n"
            log_entry += f"{'='*50}\n"
        
        # Путь к файлу webhooks.txt (создаем в корне backend)
        file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'webhooks.txt')
        
        # Записываем в файл
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        
        response = JsonResponse({
            'success': True,
            'message': 'Webhook processed and token data logged successfully',
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
