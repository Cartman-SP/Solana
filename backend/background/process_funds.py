import django

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import UserDev, AdminDev
from asgiref.sync import sync_to_async


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
        return data['funded_by']['funded_by']
    except Exception as e:
        print(f"Error: {e}")
        return ''


def process_fund(address):
    arr = []
    limit = 10
    count = 0
    admin = AdminDev()
    arr.append(UserDeb.objects.get(adress = address))
    fund = address
    while count < limit
        fund = get_funding_addresses(fund)
        dev, created = UserDev.objects.get_or_create(
            adress=fund,
            faunded=True,
        )
        arr.append(dev)
        if(created):
            count+=1
        else:
            try:
                if dev.admin:
                    return arr, dev.admin
                else:
                    return arr, admin

def process_first(address):
    arr, admin = process_fund(address)
    if(admin.id):
        for i in arr:
            i.admin = admin
    else:
        admin = admin.save()
        for i in arr:
            i.admin = admin


