from django.urls import path
from . import views

urlpatterns = [
    path('login', views.user_login),
    path('register', views.user_register),

    path('getUserById', views.get_user_by_id),
    path("vector-search", views.vector_search),
    path('decode', views.decode_token),
    path('updateuserinfo', views.update_user_info),
]
