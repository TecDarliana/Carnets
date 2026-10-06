from django.urls import path

from . import views

app_name = 'carnets'

urlpatterns = [
    path('', views.CarnetListView.as_view(), name='lista'),
    path('buscar/', views.buscar, name='buscar'),
    path('historial/', views.HistorialListView.as_view(), name='historial'),
    path('pdf/<str:ci>/', views.carnet_pdf_siglas, name='pdf'),
    path('nuevo/', views.CarnetCreateView.as_view(), name='crear'),
    path('generar-todos/', views.generar_todos, name='generar_todos'),
    path('generar/<int:empleado_pk>/', views.generar_carnet, name='generar'),
    path('<int:pk>/', views.CarnetDetailView.as_view(), name='detalle'),
    path('<int:pk>/editar/', views.CarnetUpdateView.as_view(), name='editar'),
    path('<int:pk>/eliminar/', views.CarnetDeleteView.as_view(), name='eliminar'),
    path('<int:pk>/imagen/', views.carnet_imagen, name='imagen'),
]
