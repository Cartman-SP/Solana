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
from mainapp.views import blacklist_user, whitelist_user, bonk_webhook, get_wallets

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/blacklist/', blacklist_user, name='blacklist_user'),
    path('api/whitelist/', whitelist_user, name='whitelist_user'),
    path('api/bonk/', bonk_webhook, name='bonk_webhook'),
    path('api/get_wallets/', get_wallets, name='get_wallets'),
]
