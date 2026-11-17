"""HTTP routes owned by Django. The public game API will be FastAPI."""

from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
