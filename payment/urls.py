from django.urls import path
from . import views
from .webhooks import stripe_webhook

urlpatterns = [
    path('create-intent/', views.create_intent, name='create_intent'),
    path('webhook/', views.webhook, name='webhook'),
    path("api/payments/webhook/", stripe_webhook, name="stripe-webhook"),
]
