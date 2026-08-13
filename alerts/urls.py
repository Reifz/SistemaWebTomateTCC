from django.urls import path
from . import views

urlpatterns = [path("", views.alert_list, name="alert_list"), path("<int:pk>/read/", views.mark_read, name="alert_read")]
