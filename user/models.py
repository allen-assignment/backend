from django.db import models

# Create your models here.
class User(models.Model):
    username = models.CharField(max_length=255)
    usertype = models.IntegerField()
    email = models.EmailField(max_length=255)
    password = models.CharField(max_length=255)
    birth_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username