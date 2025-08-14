from django.db import models

class AdminDev(models.Model):
    twitter = models.CharField(max_length=255,default = "",unique = False)
    blacklist = models.BooleanField(default=False)
    whitelist = models.BooleanField(default=False)
    ath = models.IntegerField(default=0)
    total_devs = models.IntegerField(default=0)

    def __str__(self):
        return self.twitter

class UserDev(models.Model):
    admin = models.ForeignKey(AdminDev, on_delete=models.CASCADE, null=True, blank=True)
    adress = models.CharField(max_length=255)
    total_tokens = models.IntegerField(default=0)
    whitelist = models.BooleanField(default=False)
    blacklist = models.BooleanField(default=False)
    ath = models.IntegerField(default=0)
    uri = models.CharField(max_length=255, null=True, blank=True)
    processed = models.BooleanField(default=False)
    faunded = models.BooleanField(default=False)
    faunded_by = models.ForeignKey("UserDev", on_delete=models.CASCADE, null=True, blank=True)
    def __str__(self):
        return self.adress

class Token(models.Model):
    address = models.CharField(max_length=255)
    dev = models.ForeignKey(UserDev, on_delete=models.CASCADE)
    scam = models.BooleanField(default=False)
    ath = models.IntegerField(default=0)
    migrated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
