from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.personas.models import Empleado

from . import siglas
from .forms import CarnetForm
from .models import Carnet, HistorialCarnet
from .services import imagen_carnet_png


class CarnetListView(LoginRequiredMixin, ListView):
    model = Carnet
    template_name = 'carnets/carnet_list.html'
    context_object_name = 'carnets'
    paginate_by = 12

    def get_queryset(self):
        return super().get_queryset().select_related('empleado')


class CarnetDetailView(LoginRequiredMixin, DetailView):
    model = Carnet
    template_name = 'carnets/carnet_detail.html'
    context_object_name = 'carnet'


class CarnetCreateView(LoginRequiredMixin, CreateView):
    model = Carnet
    form_class = CarnetForm
    template_name = 'carnets/carnet_form.html'

    def get_initial(self):
        initial = super().get_initial()
        empleado_id = self.request.GET.get('empleado')
        if empleado_id and Empleado.objects.filter(pk=empleado_id).exists():
            initial['empleado'] = empleado_id
        return initial

    def form_valid(self, form):
        form.instance.estado = Carnet.Estado.GENERADO
        return super().form_valid(form)


class CarnetUpdateView(LoginRequiredMixin, UpdateView):
    model = Carnet
    form_class = CarnetForm
    template_name = 'carnets/carnet_form.html'


class CarnetDeleteView(LoginRequiredMixin, DeleteView):
    model = Carnet
    template_name = 'carnets/carnet_confirm_delete.html'
    success_url = reverse_lazy('carnets:lista')


@login_required
def carnet_imagen(request, pk):
    carnet = get_object_or_404(Carnet, pk=pk)
    data = imagen_carnet_png(carnet)
    response = HttpResponse(data, content_type='image/png')
    modo = 'attachment' if request.GET.get('descargar') else 'inline'
    response['Content-Disposition'] = f'{modo}; filename="carnet-{carnet.numero}.png"'
    return response


@require_POST
def generar_carnet(request, empleado_pk):
    empleado = get_object_or_404(Empleado, pk=empleado_pk)
    carnet = empleado.carnets.filter(estado=Carnet.Estado.GENERADO).first()
    if not carnet:
        carnet = Carnet.objects.create(empleado=empleado, estado=Carnet.Estado.GENERADO)
        messages.success(request, f'Carnet generado para {empleado.nombre_completo}.')
    return redirect('carnets:detalle', pk=carnet.pk)


@require_POST
def generar_todos(request):
    pendientes = Empleado.objects.exclude(carnets__estado=Carnet.Estado.GENERADO).distinct()
    cantidad = 0
    for empleado in pendientes:
        Carnet.objects.create(empleado=empleado, estado=Carnet.Estado.GENERADO)
        cantidad += 1
    messages.success(request, f'{cantidad} carnet(s) generado(s).')
    return redirect('personas:lista')


@login_required
def buscar(request):
    """Busca un funcionario en SIGLAS por cédula y ofrece el PDF del carnet."""
    q = request.GET.get('q', '').strip()
    datos = None
    error = None
    foto_url = None
    if q:
        ci = ''.join(ch for ch in q if ch.isdigit())
        if not ci:
            error = 'La cédula debe contener solo números.'
        else:
            try:
                datos = siglas.buscar_funcionario(ci)
            except Exception:
                error = 'No se pudo consultar la base de datos de SIGLAS. Intente de nuevo.'
            else:
                if datos is None:
                    error = f'No se encontró ningún funcionario con cédula {ci}.'
                else:
                    foto_url = settings.SIGLAS_FOTO_URL.format(ci=datos['ci'])
    return render(request, 'carnets/buscar.html', {
        'q': q,
        'datos': datos,
        'error': error,
        'foto_url': foto_url,
    })


@login_required
def carnet_pdf_siglas(request, ci):
    """Genera y sirve el PDF del carnet para la cédula indicada."""
    if not ci.isdigit():
        raise Http404
    datos, pdf = siglas.generar_pdf(ci)
    if pdf is None:
        raise Http404
    if not request.GET.get('vista'):
        HistorialCarnet.objects.create(
            ci=datos['ci'],
            nombre=datos['nombre_completo'],
            cargo=datos['cargo'],
            departamento=datos['departamento'],
            usuario=request.user,
        )
    response = HttpResponse(pdf, content_type='application/pdf')
    modo = 'attachment' if request.GET.get('descargar') else 'inline'
    response['Content-Disposition'] = f'{modo}; filename="carnet_{ci}.pdf"'
    return response


class HistorialListView(LoginRequiredMixin, ListView):
    model = HistorialCarnet
    template_name = 'carnets/historial.html'
    context_object_name = 'registros'
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset().select_related('usuario')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(ci__icontains=q) | Q(nombre__icontains=q))
        return qs
