"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from mainapp.views import *

urlpatterns = [
    path('', home_page, name='home_page'),
    path('search/', search_results, name='search_results'),
    path('admindev/<str:twitter>/', admindev_detail, name='admindev_detail'),
    path('userdev/<str:adress>/', userdev_detail, name='userdev_detail'),
    path('token/<str:address>/', token_detail, name='token_detail'),
    path('admin/', admin.site.urls),
    path('api/blacklist/', blacklist_user, name='blacklist_user'),
    path('api/whitelist/', whitelist_user, name='whitelist_user'),
    path('api/bonk/', bonk_webhook, name='bonk_webhook'),
    path('api/get_wallets/', get_wallets, name='get_wallets'),
    path('api/admin_data', admin_data, name='get_admin_devs'),
    path('api/pump_hook/', pump_hook, name='pump_hook'),
    path('api/token_count/', token_count, name='token_count'),
    # Unified endpoint for both GET and POST to avoid 405
    path('api/auto_buy_settings/', auto_buy_settings, name='auto_buy_settings'),
]
