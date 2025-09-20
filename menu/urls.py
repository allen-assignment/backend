from django.urls import path
from .import views

urlpatterns = [
    path('category/add/',views.add_menuCategory,name='add_menuCategory'),
    path('item/add/',views.add_menuItem,name='add_menuItem'),
    path('items/',views.get_AllMenuItems,name='get_AllMenuItems'),
]

