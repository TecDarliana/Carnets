from django.urls import path

from . import views

app_name = 'carnets'

urlpatterns = [
    # Página principal: búsqueda de cédula + creación de carnets
    path('', views.credencial_crear, name='lista'),
    path('credenciales/nueva/', views.credencial_crear, name='credencial_crear'),
    path('pdf/<str:ci>/', views.carnet_pdf_siglas, name='pdf'),
    path('generar-todos/', views.generar_todos, name='generar_todos'),

    path('historial/', views.HistorialListView.as_view(), name='historial'),

    # Resguardo en MinIO (catálogo y descarga de archivos)
    path('respaldo/', views.ArchivoListView.as_view(), name='archivo_lista'),
    path('respaldo/<int:pk>/descargar/', views.archivo_descargar, name='archivo_descargar'),

    # Plantillas
    path('plantillas/', views.PlantillaListView.as_view(), name='plantilla_lista'),
    path('plantillas/nueva/', views.PlantillaCreateView.as_view(), name='plantilla_crear'),
    path('plantillas/<int:pk>/editar/', views.PlantillaUpdateView.as_view(), name='plantilla_editar'),

    # Editor visual de plantillas
    path('plantillas/editor/', views.editor_plantilla, name='plantilla_editor_nuevo'),
    path('plantillas/<int:pk>/editor/', views.editor_plantilla, name='plantilla_editor'),
    path('plantillas/guardar/', views.plantilla_guardar, name='plantilla_guardar'),
    path('plantillas/vista-previa/', views.plantilla_preview, name='plantilla_preview'),
    path('plantillas/importar/', views.plantilla_importar, name='plantilla_importar'),
    path('libreria/<str:nombre>/', views.libreria_elemento, name='libreria_elemento'),

    # Credenciales (carnets editables, manuales o desde SIGLAS)
    path('credenciales/<int:pk>/editar/', views.credencial_editar, name='credencial_editar'),
    path('credenciales/<int:pk>/pdf/', views.credencial_pdf, name='credencial_pdf'),
    path('credenciales/<int:pk>/eliminar/', views.credencial_eliminar, name='credencial_eliminar'),
    # Página pública a la que apunta el QR escaneado
    path('digital/<uuid:codigo>/', views.credencial_digital, name='credencial_digital'),
]
