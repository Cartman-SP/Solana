from django.db import models
from django.utils import timezone
from datetime import timedelta

class AdminDev(models.Model):
    twitter = models.CharField(max_length=255,default = "",unique = False)
    blacklist = models.BooleanField(default=False)
    whitelist = models.BooleanField(default=False)
    ath = models.IntegerField(default=0)
    total_devs = models.IntegerField(default=0)
    total_tokens = models.IntegerField(default=0)
    def __str__(self):
        return self.twitter

class UserDev(models.Model):
    adress = models.CharField(max_length=255)
    total_tokens = models.IntegerField(default=0)
    blacklist = models.BooleanField(default=False)
    whitelist = models.BooleanField(default=False)

    def __str__(self):
        return self.adress

def default_last_autobuy_time():
    from django.utils import timezone
    from datetime import timedelta
    return timezone.now() - timedelta(minutes=60)

class Twitter(models.Model):
    name = models.CharField(max_length=255)
    blacklist = models.BooleanField(default=False)
    whitelist = models.BooleanField(default=False)
    total_tokens = models.IntegerField(default=0)
    ath = models.IntegerField(default=0)
    total_trans = models.IntegerField(default=0)
    total_fees = models.FloatField(default=0)
    last_autobuy_time = models.DateTimeField(default=default_last_autobuy_time)
    def __str__(self):
        return self.name

class Token(models.Model):
    address = models.CharField(max_length=255)
    dev = models.ForeignKey(UserDev, on_delete=models.CASCADE)
    twitter = models.ForeignKey(Twitter, on_delete=models.CASCADE,null=True, blank=True)
    ath = models.IntegerField(default=0)
    migrated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    total_trans = models.IntegerField(default=0)
    total_fees = models.FloatField(default=0)
    bonding_curve = models.CharField(max_length=255,default="",null=True, blank=True)
    community_id = models.CharField(max_length=255,default="",null=True, blank=True)
class Settings(models.Model):
    buyer_pubkey = models.CharField(max_length=255)
    sol_amount = models.DecimalField(max_digits=16, decimal_places=8, default=0)
    slippage_percent = models.DecimalField(max_digits=16, decimal_places=8, default=0)
    priority_fee_sol = models.DecimalField(max_digits=16, decimal_places=8, default=0)
    start = models.BooleanField(default=False)
    one_token_enabled = models.BooleanField(default=False)
    whitelist_enabled = models.BooleanField(default=False)
    ath_from = models.IntegerField(default=0)
    total_trans_from = models.IntegerField(default=0)
    total_fees_from = models.FloatField(default=0)
    median = models.IntegerField(default=0)
    dev_tokens = models.IntegerField(default=0)