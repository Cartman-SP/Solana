from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from .models import AdminDev, UserDev, Token, Twitter, Settings

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
    list_display = ('name', 'blacklist', 'whitelist', 'total_tokens','ath','total_trans','total_fees')
    list_filter = ('blacklist', 'whitelist')
    search_fields = ('name',)
    ordering = ('name',)
    list_per_page = 50
    
    def get_queryset(self, request):
        return super().get_queryset(request).only('name', 'blacklist', 'whitelist', 'total_tokens', 'ath', 'total_trans', 'total_fees')

@admin.register(UserDev)
class UserDevAdmin(admin.ModelAdmin):
    list_display = ('id', 'adress', 'total_tokens')
    list_filter = (TotalTokensFilter,)
    search_fields = ('adress',)
    ordering = ('-total_tokens', 'adress')
    list_per_page = 50
    
    def get_queryset(self, request):
        return super().get_queryset(request).only('id', 'adress', 'total_tokens')

@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ('address', 'dev_adress', 'twitter_name','bonding_curve', 'ath', 'total_trans','migrated', 'created_at', 'processed','total_fees','community_id')
    list_filter = ('migrated', 'created_at', 'processed')
    search_fields = ('address', 'dev__adress','twitter__name')
    ordering = ('-created_at', 'address')
    list_per_page = 50
    date_hierarchy = 'created_at'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('dev', 'twitter')
    
    def dev_adress(self, obj):
        return obj.dev.adress if obj.dev else '-'
    dev_adress.short_description = 'Dev'
    
    def twitter_name(self, obj):
        return obj.twitter.name if obj.twitter else '-'
    twitter_name.short_description = 'Twitter'

    # Кастомная форма для текстового ввода dev/twitter
    class TokenAdminForm(forms.ModelForm):
        dev_input = forms.CharField(label='Dev adress', required=True)
        twitter_input = forms.CharField(label='Twitter name', required=False)

        class Meta:
            model = Token
            fields = '__all__'
            widgets = {
                'dev': forms.HiddenInput(),
                'twitter': forms.HiddenInput(),
            }

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if self.instance and self.instance.pk:
                self.fields['dev_input'].initial = getattr(self.instance.dev, 'adress', '')
                self.fields['twitter_input'].initial = getattr(self.instance.twitter, 'name', '') if self.instance.twitter_id else ''

        def clean(self):
            cleaned_data = super().clean()
            dev_text = cleaned_data.get('dev_input')
            twitter_text = cleaned_data.get('twitter_input')

            if not dev_text:
                raise ValidationError({'dev_input': 'Укажите adress разработчика'})

            try:
                dev_obj = UserDev.objects.get(adress=dev_text)
            except UserDev.DoesNotExist:
                raise ValidationError({'dev_input': f'UserDev с adress="{dev_text}" не найден'})

            twitter_obj = None
            if twitter_text:
                try:
                    twitter_obj = Twitter.objects.get(name=twitter_text)
                except Twitter.DoesNotExist:
                    raise ValidationError({'twitter_input': f'Twitter с name="{twitter_text}" не найден'})

            # Проставляем реальные FK в скрытые поля
            cleaned_data['dev'] = dev_obj
            self.cleaned_data['dev'] = dev_obj
            cleaned_data['twitter'] = twitter_obj
            self.cleaned_data['twitter'] = twitter_obj
            return cleaned_data

    form = TokenAdminForm

@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ('buyer_pubkey', 'sol_amount', 'slippage_percent', 'priority_fee_sol',  'start','median','total_fees_from')
    list_filter = ('start',)
    search_fields = ('buyer_pubkey',)
    ordering = ('-sol_amount',)
    list_per_page = 50
    
    fieldsets = (
        ('Основные настройки', {
            'fields': ('buyer_pubkey', 'sol_amount', 'start')
        }),
        ('Параметры торговли', {
            'fields': ('slippage_percent', 'priority_fee_sol', )
        }),
    )


