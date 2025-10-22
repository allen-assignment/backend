from django.db import models

# Create your models here.
class MenuCategory(models.Model):
    merchant_id = models.BigIntegerField(null=True, blank=True)
    category_name = models.CharField(max_length=255)
    description = models.TextField(max_length=255,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.category_name

    class Meta:
        db_table = 'menucategory'


class MenuItem(models.Model):
    category = models.ForeignKey(MenuCategory, on_delete=models.CASCADE)
    image_url = models.URLField(max_length=255)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    inventory = models.IntegerField()
    isAvailable = models.BooleanField(default=True)
    description = models.TextField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    feature_one = models.CharField(max_length=255, blank=True, null=True)
    feature_two = models.CharField(max_length=255, blank=True, null=True)
    feature_three = models.CharField(max_length=255, blank=True, null=True)



    class Meta:
        db_table = 'menuitem'

    def __str__(self):
        return self.name