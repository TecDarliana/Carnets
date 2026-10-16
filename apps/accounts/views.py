"""Administración de usuarios: alta, edición, rol, contraseña y activación.

Acceso: superusuarios y usuarios con el permiso `carnets.administrar_usuarios`
(rol Gerente). Un administrador que no sea superusuario no puede tocar las
cuentas de otros superusuarios ni desactivarse a sí mismo.
"""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, UpdateView

from .forms import UsuarioCrearForm, UsuarioEditarForm, UsuarioPasswordForm

PERMISO = 'carnets.administrar_usuarios'


class AdminUsuariosMixin(LoginRequiredMixin):
    """Exige el permiso para administrar usuarios (los superusuarios pasan).

    Los anónimos son redirigidos al login; los autenticados sin permiso
    reciben 403.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm(PERMISO):
            if not request.user.is_authenticated:
                return super().dispatch(request, *args, **kwargs)
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


def _verificar_objetivo(actor, objetivo):
    """Un administrador que no es superusuario no puede tocar superusuarios."""
    if objetivo.is_superuser and not actor.is_superuser:
        raise PermissionDenied


class UsuarioListView(AdminUsuariosMixin, ListView):
    model = User
    template_name = 'accounts/usuario_list.html'
    context_object_name = 'usuarios'
    paginate_by = 25
    ordering = 'username'

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related('groups')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(username__icontains=q) | Q(first_name__icontains=q)
                           | Q(last_name__icontains=q))
        return qs


class UsuarioCreateView(AdminUsuariosMixin, CreateView):
    model = User
    form_class = UsuarioCrearForm
    template_name = 'accounts/usuario_form.html'
    success_url = reverse_lazy('accounts:usuario_lista')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request,
                         'Usuario «%s» creado con el rol %s.'
                         % (self.object.username, form.cleaned_data['rol']))
        return response


class UsuarioUpdateView(AdminUsuariosMixin, UpdateView):
    model = User
    form_class = UsuarioEditarForm
    template_name = 'accounts/usuario_form.html'
    success_url = reverse_lazy('accounts:usuario_lista')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.has_perm(PERMISO):
            _verificar_objetivo(request.user, get_object_or_404(User, pk=kwargs['pk']))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        if form.instance.pk == self.request.user.pk and not form.cleaned_data['is_active']:
            form.add_error('is_active', 'No puedes desactivar tu propia cuenta.')
            return self.form_invalid(form)
        response = super().form_valid(form)
        messages.success(self.request, 'Usuario «%s» actualizado.' % self.object.username)
        return response


def _verificar_acceso(request, objetivo):
    """Control común de las vistas-función: login, permiso y objetivo."""
    if not request.user.is_authenticated:
        return redirect(settings.LOGIN_URL)
    if not request.user.has_perm(PERMISO):
        raise PermissionDenied
    _verificar_objetivo(request.user, objetivo)
    return None


def usuario_password(request, pk):
    """Cambia la contraseña de un usuario (solo administradores)."""
    objetivo = get_object_or_404(User, pk=pk)
    denegado = _verificar_acceso(request, objetivo)
    if denegado:
        return denegado
    if request.method == 'POST':
        form = UsuarioPasswordForm(request.POST, user=objetivo)
        if form.is_valid():
            objetivo.set_password(form.cleaned_data['password1'])
            objetivo.save(update_fields=['password'])
            messages.success(request,
                             'Contraseña de «%s» actualizada.' % objetivo.username)
            return redirect('accounts:usuario_lista')
    else:
        form = UsuarioPasswordForm(user=objetivo)
    return render(request, 'accounts/usuario_password.html',
                  {'form': form, 'objetivo': objetivo})


@require_POST
def usuario_toggle(request, pk):
    """Activa o desactiva un usuario."""
    objetivo = get_object_or_404(User, pk=pk)
    denegado = _verificar_acceso(request, objetivo)
    if denegado:
        return denegado
    if objetivo.pk == request.user.pk:
        messages.error(request, 'No puedes desactivar tu propia cuenta.')
        return redirect('accounts:usuario_lista')
    objetivo.is_active = not objetivo.is_active
    objetivo.save(update_fields=['is_active'])
    messages.success(request, 'Usuario «%s» %s.'
                     % (objetivo.username,
                        'activado' if objetivo.is_active else 'desactivado'))
    return redirect('accounts:usuario_lista')
