API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjcmVhdGVkQXQiOjE3NTM1NzAxNzU2MjEsImVtYWlsIjoiZGFuaWlsLnNoaXJraW4wMDVAZ21haWwuY29tIiwiYWN0aW9uIjoidG9rZW4tYXBpIiwiYXBpVmVyc2lvbiI6InYyIiwiaWF0IjoxNzUzNTcwMTc1fQ.W2-ic8rt8wQZptdygjc6F3Z5N8CJv1UrCkfqzdwq2vw"


async def get_all_tokens_by_address_async(wallet_address: str, max_pages: int = 10) -> dict:
    base_url = "https://pro-api.solscan.io/v2.0/account/defi/activities"
    
    headers = {
        "token": API_KEY,
        "User-Agent": "SolanaFlipper/1.0"
    }
    
    all_tokens = {}
    page = 0
    while True:
        url = f"{base_url}?address={wallet_address}&page={page}&page_size=100&activity_type=ACTIVITY_SPL_INIT_MINT&activity_type=ACTIVITY_SPL_INIT_MINT" 
        data = await response.json()
        activities = data.get('data', [])
        if not activities:
            break

        for activity in activities:
            routers = activity.get('routers', {})
            token_address = routers.get('token1')
            
            if token_address and token_address != 'undefined' and token_address not in all_tokens:
                metadata = data.get('metadata', {}).get('tokens', {})
                token_info = metadata.get(token_address, {})
                
                all_tokens[token_address] = {
                    'address': token_address,
                    'name': token_info.get('token_name', 'Unknown'),
                    'symbol': token_info.get('token_symbol', 'Unknown'),
                    'block_time': activity.get('block_time')
                }
        page += 1
        
        if len(activities) < 100:
            break
                        
    
    result = {
        'total': len(all_tokens),
        'tokens': all_tokens
    }
    
