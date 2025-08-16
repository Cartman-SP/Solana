from django.contrib import admin
from .models import AdminDev, UserDev, Token, Twitter

class TotalTokensFilter(admin.SimpleListFilter):
    title = 'Количество токенов'
    parameter_name = 'total_tokens'
    
    def lookups(self, request, model_admin):
        return (
            ('gt0', 'Больше 0'),
            ('eq0', 'Равно 0'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'gt0':
            return queryset.filter(total_tokens__gt=0)
        elif self.value() == 'eq0':
            return queryset.filter(total_tokens=0)
        return queryset

@admin.register(Twitter)
class TwitterAdmin(admin.ModelAdmin):
    list_display = ('name', 'blacklist', 'whitelist', 'total_tokens')
    list_filter = ('blacklist', 'whitelist')
    search_fields = ('name',)
    ordering = ('name',)
    list_per_page = 50

@admin.register(UserDev)
class UserDevAdmin(admin.ModelAdmin):
    list_display = ('id', 'adress', 'total_tokens')
    list_filter = (TotalTokensFilter,)
    search_fields = ('adress',)
    ordering = ('-total_tokens', 'adress')
    list_per_page = 50

@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ('address', 'dev', 'twitter', 'ath', 'migrated', 'created_at', 'processed')
    list_filter = ('migrated', 'created_at', 'processed')
    search_fields = ('address', 'dev__adress')
    ordering = ('-created_at', 'address')
    list_per_page = 50
    date_hierarchy = 'created_at'


