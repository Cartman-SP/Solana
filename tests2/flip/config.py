import os
from dotenv import load_dotenv

# Загружаем переменные окружения из config.env
load_dotenv('config.env')

def get_headers():
    """Возвращает headers для API запросов"""
    headers = {
        'accept': os.getenv('ACCEPT_HEADER'),
        'accept-encoding': os.getenv('ACCEPT_ENCODING'),
        'accept-language': os.getenv('ACCEPT_LANGUAGE'),
        'cookie': os.getenv('COOKIE'),
        'origin': os.getenv('ORIGIN'),
        'priority': os.getenv('PRIORITY'),
        'referer': os.getenv('REFERER'),
        'sec-ch-ua': os.getenv('SEC_CH_UA'),
        'sec-ch-ua-mobile': os.getenv('SEC_CH_UA_MOBILE'),
        'sec-ch-ua-platform': os.getenv('SEC_CH_UA_PLATFORM'),
        'sec-fetch-dest': os.getenv('SEC_FETCH_DEST'),
        'sec-fetch-mode': os.getenv('SEC_FETCH_MODE'),
        'sec-fetch-site': os.getenv('SEC_FETCH_SITE'),
        'user-agent': os.getenv('USER_AGENT')
    }
    
    # Фильтруем None значения
    return {k: v for k, v in headers.items() if k is not None and v is not None} 