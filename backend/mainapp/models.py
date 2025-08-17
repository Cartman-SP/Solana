from django.db import models

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

class Twitter(models.Model):
    name = models.CharField(max_length=255)
    blacklist = models.BooleanField(default=False)
    whitelist = models.BooleanField(default=False)
    total_tokens = models.IntegerField(default=0)
    ath = models.IntegerField(default=0)

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



