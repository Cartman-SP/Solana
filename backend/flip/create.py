import asyncio
import websockets
import json
import os
import sys
import django

# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import UserDev, Token, Twitter
from asgiref.sync import sync_to_async
from datetime import datetime, timezone, timedelta

async def process_create(data):
    """Создает UserDev и Token из полученных данных"""
    try:
        # Извлекаем данные
        source = data.get('source', '')
        mint = data.get('mint', '')
        user = data.get('user', '')
        name = data.get('name', '')
        symbol = data.get('symbol', '')
        uri = data.get('uri', '')
        community_id = data.get('community_id', '')
        twitter_name = data.get('twitter_name','')
        bonding_curve = data.get('bonding_curve','')
        token_created = False
        if not(twitter_name) or twitter_name == "@" or twitter_name=="@None":
            twitter_name = ""
        twitter = None
        if(twitter_name or twitter_name!= ""):
            twitter, created = await sync_to_async(Twitter.objects.get_or_create)(
                name=twitter_name,
            )
        
        user_dev, created = await sync_to_async(UserDev.objects.get_or_create)(
            adress=user,
            defaults={
                'total_tokens': 0,
            }
        )
        
        # Проверяем, что twitter существует и не в черном списке
        if twitter:
            if twitter.blacklist == False:
                token, token_created = await sync_to_async(Token.objects.get_or_create)(
                    address=mint,
                    defaults={
                        'dev': user_dev,
                        'twitter': twitter,
                        'ath': 0,
                        'migrated': False,
                        'total_trans': 0,
                        'total_fees': 0.0,
                        'bonding_curve': bonding_curve or "",
                        'community_id': community_id or "",
                    }
                )
        else:
            token, token_created = await sync_to_async(Token.objects.get_or_create)(
                    address=mint,
                    defaults={
                        'dev': user_dev,
                        'ath': 0,
                        'migrated': False,
                        'total_trans': 0,
                        'total_fees': 0.0,
                        'bonding_curve': bonding_curve or "",
                        'community_id': community_id or "",
                    }
                )

        
        if token_created:
            user_dev.total_tokens += 1
            if twitter:  # Добавляем проверку
                twitter.total_tokens +=1
                await sync_to_async(twitter.save)()
            await sync_to_async(user_dev.save)()
    except Exception as e:
        print("create",e)
        pass


