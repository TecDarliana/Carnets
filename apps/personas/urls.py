from django.urls import path

from . import views

app_name = 'personas'

urlpatterns = [
    path('', views.EmpleadoListView.as_view(), name='lista'),
    path('nuevo/', views.EmpleadoCreateView.as_view(), name='crear'),
    path('<int:pk>/', views.EmpleadoDetailView.as_view(), name='detalle'),
    path('<int:pk>/editar/', views.EmpleadoUpdateView.as_view(), name='editar'),
    path('<int:pk>/eliminar/', views.EmpleadoDeleteView.as_view(), name='eliminar'),
]
