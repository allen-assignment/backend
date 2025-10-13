

from django.contrib import admin
from .models import MenuItem, MenuCategory

# Register your models here.
admin.site.register(MenuCategory)
admin.site.register(MenuItem)