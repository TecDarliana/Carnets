from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Administración de usuarios (Gerente / superusuario)
    path('usuarios/', views.UsuarioListView.as_view(), name='usuario_lista'),
    path('usuarios/nuevo/', views.UsuarioCreateView.as_view(), name='usuario_crear'),
    path('usuarios/<int:pk>/editar/', views.UsuarioUpdateView.as_view(), name='usuario_editar'),
    path('usuarios/<int:pk>/contrasena/', views.usuario_password, name='usuario_password'),
    path('usuarios/<int:pk>/activar/', views.usuario_toggle, name='usuario_toggle'),
]
