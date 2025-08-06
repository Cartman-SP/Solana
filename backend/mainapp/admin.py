from django.contrib import admin
from .models import AdminDev, UserDev, Token

@admin.register(AdminDev)
class AdminDevAdmin(admin.ModelAdmin):
    list_display = ('twitter', 'blacklist', 'whitelist', 'ath')
    list_filter = ('blacklist', 'whitelist')
    search_fields = ('twitter',)
    ordering = ('twitter',)

@admin.register(UserDev)
class UserDevAdmin(admin.ModelAdmin):
    list_display = ('adress', 'admin', 'total_tokens', 'whitelist', 'blacklist', 'ath', 'processed')
    list_filter = ('whitelist', 'blacklist', 'processed', 'admin')
    search_fields = ('adress', 'uri')
    ordering = ('-total_tokens', 'adress')
    list_per_page = 50

@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ('address', 'dev', 'scam', 'ath', 'migrated', 'created_at')
    list_filter = ('scam', 'migrated', 'created_at')
    search_fields = ('address', 'dev__adress')
    ordering = ('-created_at', 'address')
    list_per_page = 50
    date_hierarchy = 'created_at'
