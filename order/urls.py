from django.urls import path
from .import views

urlpatterns = [
    path('getOrders/', views.get_all_orders, name='get_all_orders'),
    path('create/', views.new_order, name='new_order'),
    path('cancel/', views.cancel_order, name='cancel_order'),
]
