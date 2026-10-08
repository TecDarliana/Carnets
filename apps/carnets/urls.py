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
    path('plantillas/', views.PlantillaListView.as_view(), name='plantilla_lista'),
    path('plantillas/nueva/', views.PlantillaCreateView.as_view(), name='plantilla_crear'),
    path('plantillas/<int:pk>/editar/', views.PlantillaUpdateView.as_view(), name='plantilla_editar'),

    # Credenciales (carnets editables, manuales o desde SIGLAS)
    path('credenciales/', views.CredencialListView.as_view(), name='credencial_lista'),
    path('credenciales/nueva/', views.credencial_crear, name='credencial_crear'),
    path('credenciales/<int:pk>/editar/', views.credencial_editar, name='credencial_editar'),
    path('credenciales/<int:pk>/pdf/', views.credencial_pdf, name='credencial_pdf'),
    path('credenciales/<int:pk>/eliminar/', views.credencial_eliminar, name='credencial_eliminar'),
    # Página pública a la que apunta el QR escaneado
    path('digital/<uuid:codigo>/', views.credencial_digital, name='credencial_digital'),
]
