from django.urls import path
from . import views

urlpatterns = [
    path("", views.capture_list, name="capture_list"),
    path("new/", views.capture_create, name="capture_create"),
    path("<int:pk>/", views.capture_detail, name="capture_detail"),
    path("<int:pk>/process/", views.capture_process, name="capture_process"),
]
