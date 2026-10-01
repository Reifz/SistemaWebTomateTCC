from django.urls import path
from .views import historico

urlpatterns = [path("", historico, name="historico")]
