from django.contrib import admin
from .models import AdminDev, UserDev, Token

class AdminTwitterFilter(admin.SimpleListFilter):
    title = 'Twitter админа'
    parameter_name = 'admin_twitter'
    
    def lookups(self, request, model_admin):
        # Получаем уникальные Twitter админов
        admins = AdminDev.objects.exclude(twitter='').values_list('twitter', 'twitter').distinct()
        return admins
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(admin__twitter=self.value())
        return queryset

@admin.register(AdminDev)
class AdminDevAdmin(admin.ModelAdmin):
    list_display = ('twitter', 'blacklist', 'whitelist', 'ath')
    list_filter = ('blacklist', 'whitelist')
    search_fields = ('twitter',)
    ordering = ('twitter',)

@admin.register(UserDev)
class UserDevAdmin(admin.ModelAdmin):
    list_display = ('adress', 'admin', 'total_tokens', 'whitelist', 'blacklist', 'ath', 'processed')
    list_filter = ('whitelist', 'blacklist', 'processed', AdminTwitterFilter)
    search_fields = ('adress', 'uri')
    ordering = ('-total_tokens', 'adress')
    list_per_page = 50

@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ('address', 'dev', 'scam', 'ath', 'migrated', 'created_at','processed')
    list_filter = ('scam', 'migrated', 'created_at','processed')
    search_fields = ('address', 'dev__adress')
    ordering = ('-created_at', 'address')
    list_per_page = 50
    date_hierarchy = 'created_at'
