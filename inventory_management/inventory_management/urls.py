from django.contrib import admin
from django.urls import path

admin.site.site_header = "Inventory management Admin"
admin.site.site_title = "Inventory management Admin Portal"
admin.site.index_title = "Welcome to Inventory management"

urlpatterns = [
    path('admin/', admin.site.urls),
]
