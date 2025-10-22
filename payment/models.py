from django.db import models

class Payment(models.Model):
    order_id = models.CharField(max_length=64, db_index=True)
    stripe_payment_intent_id = models.CharField(max_length=255, unique=True)
    stripe_payment_method_id = models.CharField(max_length=255, blank=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    amount = models.IntegerField(help_text="Amount in smallest currency unit, e.g., cents")
    currency = models.CharField(max_length=10, default="usd")
    status = models.CharField(max_length=64, default="requires_payment_method")
    failure_code = models.CharField(max_length=128, blank=True)
    failure_message = models.TextField(blank=True)
    card_brand = models.CharField(max_length=32, blank=True)
    card_last4 = models.CharField(max_length=4, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payment'
        managed = False

class PaymentAttempt(models.Model):
    user_id = models.CharField(max_length=64, blank=True)
    ip = models.GenericIPAddressField(null=True)
    route = models.CharField(max_length=64)
    success = models.BooleanField(default=False)
    reason = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payment_attempt'
        managed = False
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["ip", "created_at"]),
            models.Index(fields=["user_id", "created_at"]),
        ]
