from django.urls import path

from . import views

app_name = 'personas'

urlpatterns = [
    path('', views.EmpleadoListView.as_view(), name='lista'),
]
