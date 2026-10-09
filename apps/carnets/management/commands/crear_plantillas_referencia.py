"""Crea plantillas de referencia (anverso + reverso) a partir de la librería `img/`.

Genera un `.pptx` con los elementos decorativos (banderas, footer, firma,
párrafo...) y los marcadores de texto/imagen, para usarlo como base de nuevos
diseños o para editar en el editor visual.

Uso::

    python manage.py crear_plantillas_referencia [--activar]
"""

import io

from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.carnets import diseno
from apps.carnets.models import Plantilla


def _a_marca(marca, x, y, w, h):
    return {'tipo': 'imagen', 'marca': marca, 'src': None,
            'x': x, 'y': y, 'w': w, 'h': h, 'rot': 0}


def _texto(marca, x, y, w, h, sz, bold, familia, algn):
    return {'tipo': 'texto', 'marca': marca, 'x': x, 'y': y, 'w': w, 'h': h,
            'sz': sz, 'bold': bold, 'familia': familia, 'algn': algn, 'rot': 0}


def _imagen(nombre, x, y, w, h):
    return {'tipo': 'imagen', 'src': 'lib:' + nombre, 'marca': None,
            'x': x, 'y': y, 'w': w, 'h': h, 'rot': 0}


def layout_referencia():
    anverso = {
        'nombre': 'Anverso',
        'elementos': [
            {'tipo': 'fondo', 'src': 'lib:a_fondo.png', 'x': 0, 'y': 0,
             'w': 447.0, 'h': 696.5, 'rot': 0},
            _imagen('a_bandera-contorno-top.png', 3.4, 0.0, 438.7, 339.2),
            _imagen('a_RIF-G.png', 2.1, 426.6, 22.0, 175.5),
            _imagen('a_fundayacucho-footer.png', 6.9, 645.2, 435.3, 51.3),
            _a_marca('foto', 143.28, 213.29, 171.22, 171.22),
            _texto('nombre', 39.8, 386.49, 384.07, 43.63, 24.0, False,
                   'Georama Black', 'ctr'),
            _texto('documento', 113.65, 442.78, 234.45, 36.35, 18.0, True,
                   'Georama', 'ctr'),
            _texto('cargo', 61.69, 491.08, 340.3, 36.35, 18.0, True,
                   'Georama', 'ctr'),
        ],
    }
    reverso = {
        'nombre': 'Reverso',
        'elementos': [
            {'tipo': 'fondo', 'src': 'lib:r_fondo.png', 'x': 0, 'y': 0,
             'w': 447.0, 'h': 696.5, 'rot': 0},
            _imagen('r_bandera-top.png', 9.2, 2.9, 437.8, 172.4),
            _imagen('r_parrafo.png', 45.9, 201.6, 313.1, 314.6),
            _imagen('r_firma_footer.png', 170.6, 545.0, 242.6, 138.8),
            _a_marca('code_qr', 314.21, 403.03, 104.74, 104.74),
        ],
    }
    return {'ancho': 447.0, 'alto': 696.5, 'paginas': [anverso, reverso]}


class Command(BaseCommand):
    help = 'Genera plantillas de referencia (anverso/reverso) desde la librería img/.'

    def add_arguments(self, parser):
        parser.add_argument('--activar', action='store_true',
                            help='Marca la plantilla generada como activa.')

    @transaction.atomic
    def handle(self, *args, **opciones):
        layout = layout_referencia()
        datos = diseno.layout_a_pptx(layout)

        plantilla = Plantilla.objects.filter(
            nombre='Diseño Fundación (referencia)').first()
        if plantilla is None:
            plantilla = Plantilla(nombre='Diseño Fundación (referencia)')

        plantilla.descripcion = (
            'Plantilla de referencia con los elementos de la carpeta img/ '
            'como capas independientes y marcadores editables.')
        plantilla.razon_social = plantilla.razon_social or 'Fundación Ayacucho'
        plantilla.archivo.save('diseno_referencia.pptx',
                               File(io.BytesIO(datos)), save=False)

        if opciones['activar']:
            Plantilla.objects.filter(activa=True).update(activa=False)
            plantilla.activa = True

        plantilla.save()
        self.stdout.write(self.style.SUCCESS(
            'Plantilla "%s" generada (id=%s, activa=%s).'
            % (plantilla.nombre, plantilla.pk, plantilla.activa)))