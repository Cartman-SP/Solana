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
from .models import AdminDev, Token, Twitter
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

def home_page(request):
    """Новая главная страница с live-счётчиком общего количества токенов"""
    return render(request, 'mainapp/home.html')

@require_GET
def token_count(request):
    """Возвращает текущее общее количество токенов"""
    try:
        count = Token.objects.count()
        return JsonResponse({"success": True, "count": count})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

def dashboard_page(request):
    """Страница live-дашборда проекта"""
    return render(request, 'mainapp/dashboard.html')

@require_GET
def dashboard_stats(request):
    """Возвращает сводные live-метрики по проекту"""
    try:
        from django.db.models import Sum
        total_tokens = Token.objects.count()
        total_user_devs = UserDev.objects.count()
        total_admins = AdminDev.objects.count()

        # Black/White lists
        admins_black = AdminDev.objects.filter(blacklist=True).count()
        admins_white = AdminDev.objects.filter(whitelist=True).count()
        users_black = UserDev.objects.filter(blacklist=True).count()
        users_white = UserDev.objects.filter(whitelist=True).count()

        # Aggregations по токенам
        sums = Token.objects.aggregate(
            total_trans_sum=Sum('total_trans'),
            total_fees_sum=Sum('total_fees')
        )
        total_trans_sum = int(sums.get('total_trans_sum') or 0)
        total_fees_sum = float(sums.get('total_fees_sum') or 0.0)

        # Последние токены
        latest_tokens_qs = Token.objects.select_related('dev', 'twitter').order_by('-created_at')[:10]
        latest_tokens = []
        for t in latest_tokens_qs:
            latest_tokens.append({
                'address': t.address,
                'dev_adress': getattr(t.dev, 'adress', None),
                'twitter': getattr(t.twitter, 'name', None) if hasattr(t, 'twitter') else None,
                'created_at': t.created_at.isoformat() if t.created_at else None,
                'total_trans': t.total_trans,
                'total_fees': t.total_fees,
                'processed': t.processed,
                'migrated': t.migrated,
            })

        # Настройки (полезно видеть текущие флаги)
        settings_obj = Settings.objects.first()
        settings_data = None
        if settings_obj:
            settings_data = {
                'start': settings_obj.start,
                'one_token_enabled': settings_obj.one_token_enabled,
                'whitelist_enabled': settings_obj.whitelist_enabled,
                'ath_from': settings_obj.ath_from,
                'total_trans_from': getattr(settings_obj, 'total_trans_from', 0),
                'total_fees_from': getattr(settings_obj, 'total_fees_from', 0),
                'median': getattr(settings_obj, 'median', 0),
                'dev_tokens': getattr(settings_obj, 'dev_tokens', 0),
            }

        return JsonResponse({
            'success': True,
            'stats': {
                'total_tokens': total_tokens,
                'total_user_devs': total_user_devs,
                'total_admins': total_admins,
                'admins_blacklist': admins_black,
                'admins_whitelist': admins_white,
                'users_blacklist': users_black,
                'users_whitelist': users_white,
                'total_trans_sum': total_trans_sum,
                'total_fees_sum': total_fees_sum,
            },
            'latest_tokens': latest_tokens,
            'settings': settings_data,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

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
            'median': getattr(settings, 'median', 0),
            'dev_tokens': getattr(settings, 'dev_tokens', 0),
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
        settings.dev_tokens = data.get('dev_tokens', getattr(settings, 'dev_tokens', 0))
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
                'dev_tokens': getattr(settings, 'dev_tokens', 0),
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
        settings.dev_tokens = data.get('dev_tokens', getattr(settings, 'dev_tokens', 0))
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

# Premium Dashboard Views
def premium_dashboard(request):
    """Премиальный аналитический дашборд для мониторинга цифровых активов"""
    return render(request, 'mainapp/premium_dashboard.html')

def premium_token_details(request, token_id):
    """Детальная страница токена для премиального дашборда"""
    try:
        token = Token.objects.get(id=token_id)
        context = {
            'token': token,
            'user_dev': token.dev,
            'twitter': token.twitter
        }
        return render(request, 'mainapp/premium_token_details.html', context)
    except Token.DoesNotExist:
        return render(request, 'mainapp/premium_token_details.html', {'error': 'Token not found'})

@require_GET
def premium_dashboard_data(request):
    """API для получения данных премиального дашборда"""
    try:
        from django.db.models import Sum, Count, Avg
        from django.utils import timezone
        from datetime import timedelta
        
        # Базовые метрики
        total_tokens = Token.objects.count()
        active_creators = UserDev.objects.count()
        twitter_communities = Twitter.objects.count()
        
        # Объемы и комиссии
        volume_data = Token.objects.aggregate(
            total_volume=Sum('total_trans'),
            total_fees=Sum('total_fees')
        )
        total_volume = volume_data.get('total_volume', 0) or 0
        total_fees = volume_data.get('total_fees', 0.0) or 0.0
        
        # Статистика по статусам
        verified_tokens = Token.objects.filter(processed=True).count()
        pending_tokens = Token.objects.filter(processed=False).count()
        blocked_creators = UserDev.objects.filter(blacklist=True).count()
        verified_creators = UserDev.objects.filter(whitelist=True).count()
        
        # Последние токены (для live mode)
        latest_tokens = Token.objects.select_related('dev', 'twitter').order_by('-created_at')[:20]
        tokens_data = []
        
        for token in latest_tokens:
            token_info = {
                'id': token.id,
                'name': token.name or 'Unknown',
                'symbol': token.symbol or 'UNK',
                'address': token.address,
                'creator': token.dev.adress if token.dev else None,
                'twitter': token.twitter.name if token.twitter else None,
                'ath': token.ath,
                'volume': token.total_trans,
                'fees': token.total_fees,
                'status': get_token_status(token),
                'created_at': token.created_at.isoformat() if token.created_at else None,
                'processed': token.processed,
                'twitter_got': token.twitter_got,
                'retries': token.retries,
                'bonding_curve': token.bonding_curve or 'Unknown',
                'community_id': token.community_id or 'None',
                'initial_buy': float(token.initialBuy) if token.initialBuy else 0,
                'uri': token.uri or 'None',
                'migrated': token.migrated,
                'creator_status': 'verified' if token.dev and token.dev.whitelist else 'blocked' if token.dev and token.dev.blacklist else 'pending',
                'twitter_status': 'verified' if token.twitter and token.twitter.whitelist else 'blocked' if token.twitter and token.twitter.blacklist else 'pending',
                'creator_total_tokens': token.dev.total_tokens if token.dev else 0,
                'twitter_total_tokens': token.twitter.total_tokens if token.twitter else 0,
                'twitter_ath': token.twitter.ath if token.twitter else 0,
                'twitter_total_trans': token.twitter.total_trans if token.twitter else 0,
                'twitter_total_fees': token.twitter.total_fees if token.twitter else 0
            }
            tokens_data.append(token_info)
        
        # Статистика по времени
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        
        tokens_24h = Token.objects.filter(created_at__gte=last_24h).count()
        tokens_7d = Token.objects.filter(created_at__gte=last_7d).count()
        
        # Топ создатели
        top_creators = UserDev.objects.annotate(
            token_count=Count('token')
        ).order_by('-token_count')[:10]
        
        creators_data = []
        for creator in top_creators:
            creator_info = {
                'address': creator.adress,
                'total_tokens': creator.total_tokens,
                'token_count': creator.token_count,
                'status': 'verified' if creator.whitelist else 'blocked' if creator.blacklist else 'pending'
            }
            creators_data.append(creator_info)
        
        return JsonResponse({
            'success': True,
            'stats': {
                'total_tokens': total_tokens,
                'active_creators': active_creators,
                'twitter_communities': twitter_communities,
                'total_volume': total_volume,
                'total_fees': total_fees,
                'verified_tokens': verified_tokens,
                'pending_tokens': pending_tokens,
                'blocked_creators': blocked_creators,
                'verified_creators': verified_creators,
                'tokens_24h': tokens_24h,
                'tokens_7d': tokens_7d
            },
            'tokens': tokens_data,
            'top_creators': creators_data
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@require_GET
def premium_token_search(request):
    """API для поиска токенов в премиальном дашборде"""
    try:
        query = request.GET.get('q', '').strip()
        status_filter = request.GET.get('status', '')
        sort_by = request.GET.get('sort', 'created_at')
        sort_order = request.GET.get('order', 'desc')
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        
        # Базовый queryset
        tokens = Token.objects.select_related('dev', 'twitter')
        
        # Поиск
        if query:
            tokens = tokens.filter(
                Q(name__icontains=query) |
                Q(symbol__icontains=query) |
                Q(address__icontains=query) |
                Q(dev__adress__icontains=query) |
                Q(twitter__name__icontains=query)
            )
        
        # Фильтр по статусу
        if status_filter:
            if status_filter == 'verified':
                tokens = tokens.filter(processed=True)
            elif status_filter == 'pending':
                tokens = tokens.filter(processed=False)
            elif status_filter == 'blocked':
                tokens = tokens.filter(dev__blacklist=True)
        
        # Фильтр по статусу обработки
        processing_filter = request.GET.get('processing', '')
        if processing_filter:
            if processing_filter == 'processed':
                tokens = tokens.filter(processed=True)
            elif processing_filter == 'pending':
                tokens = tokens.filter(processed=False)
        
        # Фильтр по статусу Twitter
        twitter_status_filter = request.GET.get('twitter_status', '')
        if twitter_status_filter:
            if twitter_status_filter == 'got':
                tokens = tokens.filter(twitter_got=True)
            elif twitter_status_filter == 'not_got':
                tokens = tokens.filter(twitter_got=False)
        
        # Сортировка
        if sort_order == 'desc':
            tokens = tokens.order_by(f'-{sort_by}')
        else:
            tokens = tokens.order_by(sort_by)
        
        # Пагинация
        paginator = Paginator(tokens, per_page)
        page_obj = paginator.get_page(page)
        
        # Подготовка данных
        tokens_data = []
        for token in page_obj:
            token_info = {
                'id': token.id,
                'name': token.name or 'Unknown',
                'symbol': token.symbol or 'UNK',
                'address': token.address,
                'creator': token.dev.adress if token.dev else None,
                'twitter': token.twitter.name if token.twitter else None,
                'ath': token.ath,
                'volume': token.total_trans,
                'fees': token.total_fees,
                'status': get_token_status(token),
                'created_at': token.created_at.isoformat() if token.created_at else None,
                'processed': token.processed,
                'twitter_got': token.twitter_got,
                'retries': token.retries,
                'bonding_curve': token.bonding_curve or 'Unknown',
                'community_id': token.community_id or 'None',
                'initial_buy': float(token.initialBuy) if token.initialBuy else 0,
                'uri': token.uri or 'None',
                'migrated': token.migrated,
                'creator_status': 'verified' if token.dev and token.dev.whitelist else 'blocked' if token.dev and token.dev.blacklist else 'pending',
                'twitter_status': 'verified' if token.twitter and token.twitter.whitelist else 'blocked' if token.twitter and token.twitter.blacklist else 'pending',
                'creator_total_tokens': token.dev.total_tokens if token.dev else 0,
                'twitter_total_tokens': token.twitter.total_tokens if token.twitter else 0,
                'twitter_ath': token.twitter.ath if token.twitter else 0,
                'twitter_total_trans': token.twitter.total_trans if token.twitter else 0,
                'twitter_total_fees': token.twitter.total_fees if token.twitter else 0
            }
            tokens_data.append(token_info)
        
        return JsonResponse({
            'success': True,
            'tokens': tokens_data,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': page_obj.paginator.num_pages,
                'total_count': page_obj.paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def get_token_status(token):
    """Определяет статус токена для отображения"""
    if token.dev and token.dev.blacklist:
        return 'blocked'
    elif token.dev and token.dev.whitelist:
        return 'verified'
    elif token.processed:
        return 'processed'
    else:
        return 'pending'
