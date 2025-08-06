from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from .models import UserDev
from django.views.decorators.http import require_http_methods

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
