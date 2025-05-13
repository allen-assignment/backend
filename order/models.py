from django.db import models

from user.models import User
from menu.models import MenuItem

# Create your models here.

ORDER_STATUS_CHOICES = [
    (0, 'paid'),
    (1, 'cancelled')
]
class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order_time = models.DateTimeField(auto_now_add=True)
    table_number = models.CharField(max_length=50)
    status = models.IntegerField(choices=ORDER_STATUS_CHOICES, default=0)
    total_price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'order'

    def __str__(self):
        return f"{self.user.name} - {self.order_time.strftime('%Y-%m-%d %H:%M')}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    item_price = models.DecimalField(max_digits=8, decimal_places=2)
    quantity = models.IntegerField()
    subtotal = models.DecimalField(max_digits=8, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'orderitem'

    def __str__(self):
        return "order items Success" + f"{self.quantity}"