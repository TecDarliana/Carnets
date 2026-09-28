from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.carnets.models import Carnet

from .forms import EmpleadoForm
from .models import Empleado


class EmpleadoListView(LoginRequiredMixin, ListView):
    model = Empleado
    template_name = 'personas/empleado_list.html'
    context_object_name = 'empleados'
    paginate_by = 12

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q')
        departamento = self.request.GET.get('departamento')
        if q:
            qs = qs.filter(
                Q(nombres__icontains=q) | Q(apellidos__icontains=q)
                | Q(numero_documento__icontains=q) | Q(cargo__icontains=q)
            )
        if departamento:
            qs = qs.filter(departamento=departamento)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['departamento'] = self.request.GET.get('departamento', '')
        ctx['departamentos'] = Empleado.Departamento.choices
        ctx['total_registros'] = Empleado.objects.count()
        generados = Empleado.objects.filter(
            carnets__estado='generado',
        ).distinct().count()
        ctx['carnets_generados'] = generados
        ctx['carnets_pendientes'] = ctx['total_registros'] - generados
        ctx['urls_abrir_todos'] = [
            reverse('carnets:imagen', args=[carnet.pk])
            for carnet in Carnet.objects.filter(estado=Carnet.Estado.GENERADO)
        ]
        return ctx


class EmpleadoDetailView(LoginRequiredMixin, DetailView):
    model = Empleado
    template_name = 'personas/empleado_detail.html'
    context_object_name = 'empleado'


class EmpleadoCreateView(LoginRequiredMixin, CreateView):
    model = Empleado
    form_class = EmpleadoForm
    template_name = 'personas/empleado_form.html'


class EmpleadoUpdateView(LoginRequiredMixin, UpdateView):
    model = Empleado
    form_class = EmpleadoForm
    template_name = 'personas/empleado_form.html'


class EmpleadoDeleteView(LoginRequiredMixin, DeleteView):
    model = Empleado
    template_name = 'personas/empleado_confirm_delete.html'
    success_url = reverse_lazy('personas:lista')
