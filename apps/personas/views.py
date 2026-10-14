from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView

from apps.carnets import siglas
from apps.carnets.models import HistorialCarnet


class EmpleadoListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Empleados activos de la base de datos corporativa (SIGLAS).

    Muestra foto, cédula, nombre, cargo, departamento y fecha de ingreso, con
    la marca de carnet generado (✓) o pendiente (X), y acceso a Analistas y
    Gerentes (requiere `editar_imprimir_carnets`).
    """
    template_name = 'personas/empleado_list.html'
    context_object_name = 'empleados'
    permission_required = 'carnets.editar_imprimir_carnets'
    paginate_by = 12

    def get_queryset(self):
        try:
            self.todos = siglas.listar_funcionarios()
            self.error_siglas = None
        except Exception:
            self.todos = []
            self.error_siglas = ('No se pudo consultar la base de datos de '
                                 'empleados (SIGLAS). Intente de nuevo.')

        q = (self.request.GET.get('q') or '').strip().lower()
        departamento = (self.request.GET.get('departamento') or '').strip()

        resultado = self.todos
        if q:
            resultado = [f for f in resultado
                         if q in f['nombre_completo'].lower()
                         or q in f['ci']
                         or q in (f['cargo'] or '').lower()]
        if departamento:
            resultado = [f for f in resultado
                         if f['departamento'] == departamento]
        return resultado

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        generados = set(HistorialCarnet.objects.values_list('ci', flat=True).distinct())

        todos = getattr(self, 'todos', [])
        for f in todos:
            f['carnet_generado'] = f['ci'] in generados
            f['foto_url'] = settings.SIGLAS_FOTO_URL.format(ci=f['ci'])

        ctx['total_registros'] = len(todos)
        ctx['carnets_generados'] = sum(1 for f in todos if f['carnet_generado'])
        ctx['carnets_pendientes'] = ctx['total_registros'] - ctx['carnets_generados']
        ctx['q'] = self.request.GET.get('q', '')
        ctx['departamento'] = self.request.GET.get('departamento', '')
        ctx['departamentos'] = sorted({f['departamento'] for f in todos
                                       if f['departamento']})
        ctx['error_siglas'] = getattr(self, 'error_siglas', None)
        return ctx
