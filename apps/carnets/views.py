import json
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q
from django.urls import reverse, reverse_lazy
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView
from django.template.defaultfilters import filesizeformat

from apps.personas.models import Empleado

from . import diseno, siglas
from .forms import CarnetForm, CredencialForm, PlantillaForm
from .models import Carnet, Credencial, HistorialCarnet, Plantilla
from .services import imagen_carnet_png


class PermisoCarnetMixin(PermissionRequiredMixin):
    """Exige un permiso de `carnets` (los superusuarios pasan siempre).

    Los anónimos son redirigidos al login; los autenticados sin permiso
    reciben 403.
    """
    raise_exception = True

    def get_permission_required(self):
        return ('carnets.' + self.permiso,)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied
        self.raise_exception = False
        return super().handle_no_permission()


class CarnetListView(LoginRequiredMixin, PermisoCarnetMixin, ListView):
    model = Carnet
    permiso = 'ver_carnets'
    template_name = 'carnets/carnet_list.html'
    context_object_name = 'carnets'
    paginate_by = 12

    def get_queryset(self):
        return super().get_queryset().select_related('empleado')


class CarnetDetailView(LoginRequiredMixin, PermisoCarnetMixin, DetailView):
    model = Carnet
    permiso = 'ver_carnets'
    template_name = 'carnets/carnet_detail.html'
    context_object_name = 'carnet'


class CarnetCreateView(LoginRequiredMixin, PermisoCarnetMixin, CreateView):
    model = Carnet
    permiso = 'editar_imprimir_carnets'
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


class CarnetUpdateView(LoginRequiredMixin, PermisoCarnetMixin, UpdateView):
    model = Carnet
    permiso = 'editar_imprimir_carnets'
    form_class = CarnetForm
    template_name = 'carnets/carnet_form.html'


class CarnetDeleteView(LoginRequiredMixin, PermisoCarnetMixin, DeleteView):
    model = Carnet
    permiso = 'editar_imprimir_carnets'
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
    if not _permiso_requerido(request.user, 'ver_carnets'):
        raise PermissionDenied
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
@xframe_options_sameorigin
def carnet_pdf_siglas(request, ci):
    """Genera y sirve el PDF del carnet para la cédula indicada.

    La vista previa (`?vista=previa`) solo requiere `ver_carnets`; descargar o
    imprimir exige `editar_imprimir_carnets`.
    """
    if not ci.isdigit():
        raise Http404
    es_previa = bool(request.GET.get('vista'))
    if es_previa:
        if not _permiso_requerido(request.user, 'ver_carnets'):
            raise PermissionDenied
    elif not _permiso_requerido(request.user, 'editar_imprimir_carnets',
                                'crear_carnet_manual'):
        raise PermissionDenied
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


class HistorialListView(LoginRequiredMixin, PermisoCarnetMixin, ListView):
    model = HistorialCarnet
    permiso = 'ver_carnets'
    template_name = 'carnets/historial.html'
    context_object_name = 'registros'
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset().select_related('usuario')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(ci__icontains=q) | Q(nombre__icontains=q))
        return qs


class PlantillaListView(LoginRequiredMixin, PermisoCarnetMixin, ListView):
    model = Plantilla
    permiso = 'ver_carnets'
    template_name = 'carnets/plantilla_list.html'
    context_object_name = 'plantillas'
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset().order_by('-activa', 'nombre')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(nombre__icontains=q)
        return qs


class PlantillaCreateView(LoginRequiredMixin, PermisoCarnetMixin, CreateView):
    model = Plantilla
    permiso = 'editar_imprimir_carnets'
    form_class = PlantillaForm
    template_name = 'carnets/plantilla_form.html'
    success_url = reverse_lazy('carnets:plantilla_lista')

    def form_valid(self, form):
        # Si esta plantilla se marca como activa, desactivar las demás
        if form.instance.activa:
            Plantilla.objects.filter(activa=True).exclude(pk=form.instance.pk).update(activa=False)
        return super().form_valid(form)


class PlantillaUpdateView(LoginRequiredMixin, PermisoCarnetMixin, UpdateView):
    model = Plantilla
    permiso = 'editar_imprimir_carnets'
    form_class = PlantillaForm
    template_name = 'carnets/plantilla_form.html'
    success_url = reverse_lazy('carnets:plantilla_lista')

    def form_valid(self, form):
        # Si esta plantilla se marca como activa, desactivar las demás
        if form.instance.activa:
            Plantilla.objects.filter(activa=True).exclude(pk=form.instance.pk).update(activa=False)
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Editor visual de plantillas (layout JSON ⇄ PPTX)
# ---------------------------------------------------------------------------

ANCHO_DEFECTO = 447.0
ALTO_DEFECTO = 696.5


def _layout_plantilla_activa():
    """Layout de la plantilla activa (o de la primera con archivo)."""
    plantilla = Plantilla.objects.filter(archivo__isnull=False).exclude(
        archivo='').order_by('-activa', '-id').first()
    if plantilla:
        try:
            return diseno.plantilla_a_layout(plantilla.archivo.path), plantilla
        except Exception:
            pass
    return _layout_vacio(), None


def _layout_vacio():
    return {'ancho': ANCHO_DEFECTO, 'alto': ALTO_DEFECTO,
            'paginas': [{'nombre': 'Anverso', 'elementos': []},
                        {'nombre': 'Reverso', 'elementos': []}]}


def _json_body(request):
    try:
        return json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return None


def editor_plantilla(request, pk=None):
    """Editor visual. Sin `pk` parte de la plantilla activa o de un lienzo vacío."""
    if not request.user.is_authenticated:
        return redirect(settings.LOGIN_URL)
    if not _permiso_requerido(request.user, 'editar_imprimir_carnets'):
        raise PermissionDenied

    plantilla = None
    if pk:
        plantilla = get_object_or_404(Plantilla, pk=pk)
        try:
            layout = diseno.plantilla_a_layout(plantilla.archivo.path)
        except Exception:
            layout = _layout_vacio()
    else:
        # Sin pk: lienzo en blanco (o el layout de la plantilla activa si se pide).
        if request.GET.get('desde_activa'):
            layout, plantilla = _layout_plantilla_activa()
        else:
            layout = _layout_vacio()

    return render(request, 'carnets/editor.html', {
        'plantilla': plantilla,
        'layout': layout,
        'libreria': diseno.libreria(),
        'ancho': layout['ancho'],
        'alto': layout['alto'],
        'guardar_url': reverse('carnets:plantilla_guardar'),
        'preview_url': reverse('carnets:plantilla_preview'),
        'importar_url': reverse('carnets:plantilla_importar'),
    })


@require_POST
def plantilla_guardar(request):
    """Genera el PPTX desde el layout del editor y lo guarda en una Plantilla."""
    if not request.user.is_authenticated:
        return redirect(settings.LOGIN_URL)
    if not _permiso_requerido(request.user, 'editar_imprimir_carnets'):
        raise PermissionDenied

    datos = _json_body(request)
    if not datos or 'layout' not in datos:
        return HttpResponse('Datos inválidos', status=400)

    layout = datos['layout']
    try:
        contenido = diseno.layout_a_pptx(layout)
    except Exception as exc:
        return HttpResponse('No se pudo generar la plantilla: %s' % exc, status=400)

    plantilla = None
    if datos.get('pk'):
        plantilla = get_object_or_404(Plantilla, pk=datos['pk'])
    if plantilla is None:
        plantilla = Plantilla()

    plantilla.nombre = (datos.get('nombre') or plantilla.nombre
                        or 'Plantilla sin nombre')
    plantilla.descripcion = datos.get('descripcion', plantilla.descripcion or '')
    plantilla.razon_social = datos.get('razon_social', plantilla.razon_social or '')
    plantilla.telefono = datos.get('telefono', plantilla.telefono or '')
    plantilla.correo = datos.get('correo', plantilla.correo or '')

    # Los enlaces marcador↔asset viajan dentro del propio PPTX (descr de la
    # forma como "__asset__:lib:..."), así que no se toca la descripcion.

    plantilla.archivo.save('plantilla_%s.pptx' % plantilla.pk if plantilla.pk else 'plantilla.pptx',
                           ContentFile(contenido), save=False)
    if datos.get('activa'):
        Plantilla.objects.filter(activa=True).exclude(pk=plantilla.pk).update(activa=False)
        plantilla.activa = True
    plantilla.save()

    return JsonResponse({
        'ok': True,
        'pk': plantilla.pk,
        'editor_url': reverse('carnets:plantilla_editor', args=[plantilla.pk]),
        'lista_url': reverse('carnets:plantilla_lista'),
    })


@require_POST
def plantilla_preview(request):
    """Renderiza un PDF (vista previa) a partir del layout enviado."""
    if not request.user.is_authenticated:
        return redirect(settings.LOGIN_URL)
    if not _permiso_requerido(request.user, 'editar_imprimir_carnets'):
        raise PermissionDenied

    datos = _json_body(request)
    if not datos or 'layout' not in datos:
        return HttpResponse('Datos inválidos', status=400)
    try:
        contenido = diseno.layout_a_pptx(datos['layout'])
        with tempfile.NamedTemporaryFile(suffix='.pptx', delete=False) as fh:
            fh.write(contenido)
            ruta = fh.name
        campos = datos.get('campos') or {}
        campos.setdefault('nombre', 'Nombre Apellido')
        campos.setdefault('cargo', 'Cargo de ejemplo')
        campos.setdefault('documento', '12345678')
        pdf = siglas.render_pdf(campos, plantilla_ruta=ruta)
    except Exception as exc:
        return HttpResponse('No se pudo generar la vista previa: %s' % exc, status=400)
    finally:
        try:
            Path(ruta).unlink()
        except Exception:
            pass

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="vista_previa.pdf"'
    return response


@require_POST
def plantilla_importar(request):
    """Convierte un `.pptx` subido al formato de layout del editor."""
    if not request.user.is_authenticated:
        return redirect(settings.LOGIN_URL)
    if not _permiso_requerido(request.user, 'editar_imprimir_carnets'):
        raise PermissionDenied

    archivo = request.FILES.get('archivo')
    if not archivo:
        return HttpResponse('Falta el archivo', status=400)
    try:
        with tempfile.NamedTemporaryFile(suffix='.pptx', delete=False) as fh:
            for trozo in archivo.chunks():
                fh.write(trozo)
            ruta = fh.name
        layout = diseno.plantilla_a_layout(ruta)
    except Exception as exc:
        return HttpResponse('No se pudo leer el PPTX: %s' % exc, status=400)
    finally:
        try:
            Path(ruta).unlink()
        except Exception:
            pass
    return JsonResponse({'ok': True, 'layout': layout})


def libreria_elemento(request, nombre):
    """Sirve una imagen de la librería `img/` para el editor."""
    if not request.user.is_authenticated:
        return redirect(settings.LOGIN_URL)
    if not _permiso_requerido(request.user, 'editar_imprimir_carnets'):
        raise PermissionDenied
    if Path(nombre).name != nombre:
        raise Http404
    ruta = diseno.LIBRERIA_DIR / nombre
    if not ruta.exists():
        raise Http404
    from django.http import FileResponse
    return FileResponse(ruta.open('rb'))


# ---------------------------------------------------------------------------
# Credenciales: carnets editables, con origen manual o desde SIGLAS
# ---------------------------------------------------------------------------

def _permiso_requerido(user, *codenames):
    """True si el usuario tiene alguno de los permisos indicados."""
    if user.is_superuser:
        return True
    return any(user.has_perm('carnets.' + c) for c in codenames)


def _foto_credentialial(credencial):
    """Bytes de la foto de la credencial (o None si no hay)."""
    if not credencial.foto:
        return None
    try:
        with credencial.foto.open('rb') as fh:
            return fh.read()
    except Exception:
        return None


def _pdf_credencial(credencial, request=None, previa=False):
    """Genera el PDF del carnet apuntando el QR a su página pública digital."""
    campos = {
        'nombre': credencial.nombre_completo,
        'cargo': credencial.cargo,
        'documento': credencial.documento,
    }
    plantilla = Plantilla.objects.filter(activa=True).exclude(
        archivo='',
    ).order_by('-id').first()
    if plantilla:
        campos.setdefault('razon_social', plantilla.razon_social)
        campos.setdefault('telefono', plantilla.telefono)
        campos.setdefault('correo', plantilla.correo)

    qr_texto = None
    if request is not None and credencial.pk:
        qr_texto = request.build_absolute_uri(
            reverse('carnets:credencial_digital', args=[credencial.codigo]))

    return siglas.render_pdf(
        campos,
        foto=_foto_credentialial(credencial),
        qr_texto=qr_texto,
        titulo='Carnet %s - %s' % (credencial.documento or '—',
                                   credencial.nombre_completo),
    )


class CredencialListView(LoginRequiredMixin, PermisoCarnetMixin, ListView):
    model = Credencial
    permiso = 'ver_carnets'
    template_name = 'carnets/credencial_list.html'
    context_object_name = 'credenciales'
    paginate_by = 12

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(nombre_completo__icontains=q) |
                           Q(documento__icontains=q) |
                           Q(cargo__icontains=q))
        return qs


def credencial_crear(request):
    """Crea un carnet desde SIGLAS (cédula) o con datos manuales."""
    if not request.user.is_authenticated:
        return redirect(settings.LOGIN_URL)
    if not _permiso_requerido(request.user, 'crear_carnet_manual',
                              'editar_imprimir_carnets'):
        raise PermissionDenied

    origen = request.GET.get('origen', 'siglas').lower()
    q = request.GET.get('q', '').strip()
    datos = None
    error = None
    foto_url = None

    if q and origen == 'siglas':
        ci = ''.join(ch for ch in q if ch.isdigit())
        if not ci:
            error = 'La cédula debe contener solo números.'
        else:
            try:
                datos = siglas.buscar_funcionario(ci)
            except Exception:
                error = 'No se pudo consultar la base de datos de SIGLAS.'
            else:
                if datos is None:
                    error = f'No se encontró ningún funcionario con cédula {ci}.'
                else:
                    foto_url = settings.SIGLAS_FOTO_URL.format(ci=datos['ci'])

    inicial = {}
    if datos:
        inicial = {
            'nombre_completo': datos['nombre_completo'],
            'documento': datos['ci'],
            'cargo': datos['cargo'],
        }

    form = CredencialForm(request.POST or None, request.FILES or None,
                          initial=inicial)
    ci_origen = datos['ci'] if datos else ''

    if request.method == 'POST' and form.is_valid():
        # Cédula de origen: si el usuario no cambió el documento, se conserva
        # el de SIGLAS para poder descargar la foto si no se subió otra.
        doc = form.cleaned_data['documento']
        origen_final = 'manual'
        origen_ci = ''
        if doc:
            try:
                if siglas.buscar_funcionario(doc) is not None:
                    origen_final = 'siglas'
                    origen_ci = doc
            except Exception:
                pass

        credencial = form.save(commit=False)
        credencial.origen = origen_final
        credencial.ci_origen = origen_ci
        credencial.creado_por = request.user
        credencial.save()

        if not credencial.foto and origen_ci:
            foto_bytes = siglas.descargar_foto(origen_ci)
            if foto_bytes:
                credencial.foto.save(
                    f'{origen_ci}.jpg', ContentFile(foto_bytes), save=True)

        messages.success(request,
                         f'Carnet de {credencial.nombre_completo} creado. '
                         'Puedes editar la información antes de imprimirlo.')
        return redirect('carnets:credencial_editar', pk=credencial.pk)

    return render(request, 'carnets/credencial_form.html', {
        'form': form,
        'origen': origen,
        'q': q,
        'datos': datos,
        'error': error,
        'foto_url': foto_url,
        'ci_origen': ci_origen,
    })


@require_POST
def credencial_eliminar(request, pk):
    if not request.user.is_authenticated:
        return redirect(settings.LOGIN_URL)
    if not _permiso_requerido(request.user, 'editar_imprimir_carnets'):
        raise PermissionDenied
    credencial = get_object_or_404(Credencial, pk=pk)
    credencial.delete()
    messages.success(request, 'Carnet eliminado.')
    return redirect('carnets:credencial_lista')


def credencial_editar(request, pk):
    """Edita los datos del carnet antes de imprimirlo y ofrece la vista previa."""
    if not request.user.is_authenticated:
        return redirect(settings.LOGIN_URL)
    if not _permiso_requerido(request.user, 'editar_imprimir_carnets',
                              'crear_carnet_manual'):
        raise PermissionDenied
    credencial = get_object_or_404(Credencial, pk=pk)
    form = CredencialForm(request.POST or None, request.FILES or None,
                          instance=credencial)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Datos actualizados.')
        return redirect('carnets:credencial_editar', pk=credencial.pk)

    return render(request, 'carnets/credencial_editar.html', {
        'credencial': credencial,
        'form': form,
        'pdf_url': reverse('carnets:credencial_pdf', args=[credencial.pk]),
        'digital_url': reverse('carnets:credencial_digital', args=[credencial.codigo]),
    })


@xframe_options_sameorigin
def credencial_pdf(request, pk):
    """Sirve el PDF del carnet (anverso + dorso) con QR a la página digital."""
    if not request.user.is_authenticated:
        return redirect(settings.LOGIN_URL)
    if not _permiso_requerido(request.user, 'editar_imprimir_carnets',
                              'crear_carnet_manual'):
        raise PermissionDenied
    credencial = get_object_or_404(Credencial, pk=pk)
    pdf = _pdf_credencial(credencial, request=request)

    previa = bool(request.GET.get('vista')) or bool(request.GET.get('previa'))
    if not previa:
        HistorialCarnet.objects.create(
            ci=credencial.documento or '—',
            nombre=credencial.nombre_completo,
            cargo=credencial.cargo,
            departamento='Credencial',
            usuario=request.user,
        )

    response = HttpResponse(pdf, content_type='application/pdf')
    modo = 'attachment' if request.GET.get('descargar') else 'inline'
    response['Content-Disposition'] = (
        f'{modo}; filename="carnet_{credencial.documento or credencial.pk}.pdf"')
    return response


def credencial_digital(request, codigo):
    """Página pública (sin login) a la que apunta el QR del carnet."""
    credencial = get_object_or_404(Credencial, codigo=codigo)
    plantilla = Plantilla.objects.filter(activa=True).order_by('-id').first()
    return render(request, 'carnets/credencial_digital.html', {
        'credencial': credencial,
        'plantilla': plantilla,
    })
