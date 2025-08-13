from django.contrib import admin
from .models import AdminDev, UserDev, Token

class HasAdminFilter(admin.SimpleListFilter):
    title = 'Наличие админа'
    parameter_name = 'has_admin'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', 'Да'),
            ('no', 'Нет'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(admin__isnull=False)
        elif self.value() == 'no':
            return queryset.filter(admin__isnull=True)
        return queryset

@admin.register(AdminDev)
class AdminDevAdmin(admin.ModelAdmin):
    list_display = ('twitter', 'blacklist', 'whitelist', 'ath',"total_devs")
    list_filter = ('blacklist', 'whitelist')
    search_fields = ('twitter',)
    ordering = ('twitter','total_devs')

@admin.register(UserDev)
class UserDevAdmin(admin.ModelAdmin):
    list_display = ('adress', 'admin' , 'whitelist', 'blacklist', 'ath', 'processed','total_tokens')
    list_filter = ('whitelist', 'blacklist', 'processed', HasAdminFilter)
    search_fields = ('adress', 'uri', 'admin__twitter')
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


