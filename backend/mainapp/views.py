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
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404
from .models import AdminDev, Token
from django.shortcuts import redirect
from .models import Settings
from django.views.decorators.http import require_GET, require_POST

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
            user_dev = token.twitter
            
            if user_dev:
                user_dev.blacklist = True
                user_dev.save()
                
                response = JsonResponse({
                    'success': True,
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
            user_dev = token.twitter
            
            if user_dev:
                user_dev.whitelist = True
                user_dev.save()
                
                response = JsonResponse({
                    'success': True,
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
    
    # Формируем URL для входящих трансферов (flow=in), чтобы получить только фондирующие адреса
    url = f"{base_url}?address={wallet_address}"
    
    try:
        data = requests.get(url = url, headers=headers).json()
        data = data.get('data', [])
        return data
    except Exception as e:
        print(f"Error: {e}")
        return []

def get_creator(token_address):
    base_url = "https://pro-api.solscan.io/v2.0/token/metadata"
    
    headers = {
        "token": api_key,
        "User-Agent": "SolanaFlipper/1.0"
    }

    url = f"{base_url}?address={token_address}"
    
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

@csrf_exempt
def get_wallets(request):
    token_address = request.GET.get('token_address')
    token_address = "5RbT1RN87YSCsDoy2mVz6nKhBBN6SZLWwXnLHzmDT3bv"

    try:
        return JsonResponse({"data":search_wallet(token_address)})
    except Exception as e:
        return JsonResponse({"success":"False",'error':str(e),'token':token_address})

def search_page(request):
    """Главная страница с поисковой строкой"""
    return render(request, 'mainapp/search.html')

def search_results(request):
    """Обработка поиска и редирект на соответствующую страницу"""
    query = request.GET.get('q', '').strip()
    
    if not query:
        return render(request, 'mainapp/search.html', {'error': 'Введите поисковый запрос'})
    
    # Поиск по AdminDev.twitter
    try:
        admin = AdminDev.objects.get(twitter__iexact=query)
        return redirect('admindev_detail', twitter=admin.twitter)
    except AdminDev.DoesNotExist:
        pass
    
    # Поиск по UserDev.adress
    try:
        user_dev = UserDev.objects.get(adress__iexact=query)
        return redirect('userdev_detail', adress=user_dev.adress)
    except UserDev.DoesNotExist:
        pass
    
    # Поиск по Token.address
    try:
        token = Token.objects.get(address__iexact=query)
        return redirect('token_detail', address=token.address)
    except Token.DoesNotExist:
        pass
    
    # Если ничего не найдено
    return render(request, 'mainapp/search.html', {
        'error': f'Ничего не найдено по запросу: {query}',
        'query': query
    })

def admindev_detail(request, twitter):
    """Страница с информацией об админе и списком UserDev"""
    admin = get_object_or_404(AdminDev, twitter=twitter)
    
    # Получаем все UserDev для этого админа
    user_devs = UserDev.objects.filter(admin=admin)
    
    # Сортировка
    sort_by = request.GET.get('sort', 'id')
    order = request.GET.get('order', 'desc')
    
    if order == 'desc':
        user_devs = user_devs.order_by(f'-{sort_by}')
    else:
        user_devs = user_devs.order_by(sort_by)
    
    # Пагинация
    paginator = Paginator(user_devs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'admin': admin,
        'page_obj': page_obj,
        'sort_by': sort_by,
        'order': order,
        'total_devs': user_devs.count()
    }
    
    return render(request, 'mainapp/admindev_detail.html', context)

def userdev_detail(request, adress):
    """Страница с информацией о UserDev и списком токенов"""
    user_dev = get_object_or_404(UserDev, adress=adress)
    
    # Получаем все токены для этого UserDev
    tokens = Token.objects.filter(dev=user_dev)
    
    # Сортировка
    sort_by = request.GET.get('sort', 'created_at')
    order = request.GET.get('order', 'desc')
    
    if order == 'desc':
        tokens = tokens.order_by(f'-{sort_by}')
    else:
        tokens = tokens.order_by(sort_by)
    
    # Пагинация
    paginator = Paginator(tokens, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'user_dev': user_dev,
        'page_obj': page_obj,
        'sort_by': sort_by,
        'order': order,
        'total_tokens': tokens.count()
    }
    
    return render(request, 'mainapp/userdev_detail.html', context)

def token_detail(request, address):
    """Страница с информацией о токене"""
    token = get_object_or_404(Token, address=address)
    
    context = {
        'token': token,
        'user_dev': token.dev,
        'admin': token.dev.admin if token.dev.admin else None
    }
    
    return render(request, 'mainapp/token_detail.html', context)


from django.http import JsonResponse
from .models import AdminDev, UserDev
from django.views.decorators.http import require_GET

@require_GET
def admin_data(request):
    twitter = request.GET.get('twitter')
    if not twitter:
        return JsonResponse({'error': 'Twitter handle is required'}, status=400)
    
    try:
        admin = AdminDev.objects.get(twitter=twitter)
    except AdminDev.DoesNotExist:
        return JsonResponse({'error': 'Admin not found'}, status=404)
    
    # Get all UserDevs for this admin
    user_devs = UserDev.objects.filter(admin=admin).select_related('faunded_by')
    
    # Prepare response data
    data = []
    for user_dev in user_devs:
        data.append({
            'adress': user_dev.adress,
            'faunded_by': user_dev.faunded_by.adress if user_dev.faunded_by else None,
            'total_tokens': user_dev.total_tokens,
            'whitelist': user_dev.whitelist,
            'blacklist': user_dev.blacklist,
            'ath': user_dev.ath,
            'processed': user_dev.processed,
            'faunded': user_dev.faunded
        })
    
    return JsonResponse(data, safe=False)


@csrf_exempt
def pump_hook(request):
    try:
        data = json.loads(request.body)
        with open('pump_hook.txt', 'a') as f:
            f.write(json.dumps(data, indent=2))
        return JsonResponse({'success': True})
    except Exception as e:
        with open('pump_hook.txt', 'a') as f:
            f.write(str(e)+"\n"+str(request.body))
        return JsonResponse({'success': True})


@csrf_exempt
@require_GET
def get_auto_buy_settings(request):
    try:
        settings = Settings.objects.first()
        if not settings:
            settings = Settings.objects.create()
        data = {
            'start': settings.start,
            'one_token_enabled': settings.one_token_enabled,
            'whitelist_enabled': settings.whitelist_enabled,
            'ath_from': settings.ath_from,
            'total_trans_from': getattr(settings, 'total_trans_from', 0),
            'total_fees_from': getattr(settings, 'total_fees_from', 0),
            'buyer_pubkey': settings.buyer_pubkey,
            'sol_amount': str(settings.sol_amount),
            'slippage_percent': str(settings.slippage_percent),
            'priority_fee_sol': str(settings.priority_fee_sol),
        }
        response = JsonResponse({'success': True, 'settings': data})
        response["Access-Control-Allow-Origin"] = "*"
        return response
    except Exception as e:
        response = JsonResponse({'success': False, 'error': str(e)}, status=500)
        response["Access-Control-Allow-Origin"] = "*"
        return response

@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def update_auto_buy_settings(request):
    if request.method == "OPTIONS":
        response = JsonResponse({})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type"
        return response
    try:
        data = json.loads(request.body)
        settings = Settings.objects.first()
        if not settings:
            settings = Settings.objects.create()
        settings.start = data.get('start', settings.start)
        settings.one_token_enabled = data.get('one_token_enabled', settings.one_token_enabled)
        settings.whitelist_enabled = data.get('whitelist_enabled', settings.whitelist_enabled)
        settings.ath_from = data.get('ath_from', settings.ath_from)
        settings.total_trans_from = data.get('total_trans_from', getattr(settings, 'total_trans_from', 0))
        settings.total_fees_from = data.get('total_fees_from', getattr(settings, 'total_fees_from', 0))
        settings.median = data.get('median', getattr(settings, 'median', 0))
        settings.buyer_pubkey = data.get('buyer_pubkey', settings.buyer_pubkey)
        settings.sol_amount = data.get('sol_amount', settings.sol_amount)
        settings.slippage_percent = data.get('slippage_percent', settings.slippage_percent)
        settings.priority_fee_sol = data.get('priority_fee_sol', settings.priority_fee_sol)
        settings.save()
        response = JsonResponse({'success': True})
        response["Access-Control-Allow-Origin"] = "*"
        return response
        
    except Exception as e:
        response = JsonResponse({'success': False, 'error': str(e)}, status=500)
        response["Access-Control-Allow-Origin"] = "*"
        return response


# Unified endpoint for GET and POST on the same URL to avoid 405
@csrf_exempt
@require_http_methods(["GET", "POST", "OPTIONS"])
def auto_buy_settings(request):
    # Handle CORS preflight
    if request.method == "OPTIONS":
        response = JsonResponse({})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    if request.method == "GET":
        try:
            settings = Settings.objects.first()
            if not settings:
                settings = Settings.objects.create()
            data = {
                'start': settings.start,
                'one_token_enabled': settings.one_token_enabled,
                'whitelist_enabled': settings.whitelist_enabled,
                'ath_from': settings.ath_from,
                'total_trans_from': getattr(settings, 'total_trans_from', 0),
                'total_fees_from': getattr(settings, 'total_fees_from', 0),
                'median': getattr(settings, 'median', 0),
                'buyer_pubkey': settings.buyer_pubkey,
                'sol_amount': str(settings.sol_amount),
                'slippage_percent': str(settings.slippage_percent),
                'priority_fee_sol': str(settings.priority_fee_sol),
            }
            response = JsonResponse({'success': True, 'settings': data})
            response["Access-Control-Allow-Origin"] = "*"
            return response
        except Exception as e:
            response = JsonResponse({'success': False, 'error': str(e)}, status=500)
            response["Access-Control-Allow-Origin"] = "*"
            return response

    # POST
    try:
        data = json.loads(request.body)
        settings = Settings.objects.first()
        if not settings:
            settings = Settings.objects.create()
        settings.start = data.get('start', settings.start)
        settings.one_token_enabled = data.get('one_token_enabled', settings.one_token_enabled)
        settings.whitelist_enabled = data.get('whitelist_enabled', settings.whitelist_enabled)
        settings.ath_from = data.get('ath_from', settings.ath_from)
        settings.total_trans_from = data.get('total_trans_from', getattr(settings, 'total_trans_from', 0))
        settings.total_fees_from = data.get('total_fees_from', getattr(settings, 'total_fees_from', 0))
        settings.median = data.get('median', getattr(settings, 'median', 0))
        settings.buyer_pubkey = data.get('buyer_pubkey', settings.buyer_pubkey)
        settings.sol_amount = data.get('sol_amount', settings.sol_amount)
        settings.slippage_percent = data.get('slippage_percent', settings.slippage_percent)
        settings.priority_fee_sol = data.get('priority_fee_sol', settings.priority_fee_sol)
        settings.save()
        response = JsonResponse({'success': True})
        response["Access-Control-Allow-Origin"] = "*"
        return response
    except Exception as e:
        response = JsonResponse({'success': False, 'error': str(e)}, status=500)
        response["Access-Control-Allow-Origin"] = "*"
        return response
