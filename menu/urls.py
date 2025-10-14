from django.urls import path
from .import views

urlpatterns = [
    path('category/add/',views.add_menuCategory,name='add_menuCategory'),
    path('item/add/',views.add_menuItem,name='add_menuItem'),
    path('items/',views.get_AllMenuItems,name='get_AllMenuItems'),
    path("ocr/upload/", views.menu_ocr_upload, name="menu-ocr-upload"),
    path('ocr/import/', views.ocr_import, name='menu_ocr_import'),
    path('item/update/', views.update_menuItem, name='update_menuItem'),
    path('item/delete/', views.delete_menuItem, name='delete_menuItem'),
    path('categories/', views.get_AllMenuCategories, name='get_AllMenuCategories'),
]

