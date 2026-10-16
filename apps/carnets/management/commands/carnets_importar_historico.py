"""Indexa en la BD los carnets y fotos históricos resguardados en MinIO.

Recorre los objetos replicados bajo ``historico/`` (subidos previamente con
``mc mirror``, ver docs/MANUAL_TALENTO_HUMANO.md), extrae la cédula del
nombre del archivo (ej. ``Carnet_V12345678.pdf``, ``foto_V12345678.jpg``),
consulta los datos actuales en SIGLAS y registra la entrada en el catálogo
(``ArchivoCarnet``) para su visualización en la tabla de resguardo.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.carnets import minio_storage, siglas
from apps.carnets.models import ArchivoCarnet
from django.conf import settings


class Command(BaseCommand):
    help = ('Cataloga los PDFs y fotos históricos resguardados en MinIO '
            '(prefijo historico/) mapeando cada archivo con la cédula del '
            'funcionario.')

    def add_arguments(self, parser):
        parser.add_argument('--prefijo', default=None,
                            help='Prefijo de objetos a indexar '
                                 '(por defecto: historico/).')
        parser.add_argument('--dry-run', action='store_true',
                            help='Solo lista lo que se indexaría, sin escribir.')

    def handle(self, *args, **options):
        cfg = settings.MINIO
        prefijo = options['prefijo'] or cfg.get('PREFIJO_HISTORICO', 'historico/')
        dry_run = options['dry_run']

        if minio_storage.cliente() is None:
            raise CommandError('MinIO no está configurado (faltan credenciales '
                               'en las variables MINIO_*).')

        # (bucket, tipo) a recorrer
        rutas = [
            (cfg['BUCKET_CARNETS'], ArchivoCarnet.Tipo.CARNET),
            (cfg['BUCKET_FOTOS'], ArchivoCarnet.Tipo.FOTO),
        ]

        total = nuevos = actualizados = sin_ci = 0
        for bucket, tipo in rutas:
            for obj in minio_storage.listar(bucket, prefijo):
                total += 1
                nombre_archivo = minio_storage.ci_de_nombre(obj['objeto'])
                if not nombre_archivo:
                    sin_ci += 1
                    self.stdout.write(self.style.WARNING(
                        f'  [sin cédula] {bucket}/{obj["objeto"]}'))
                    continue

                nombre = cargo = departamento = ''
                try:
                    datos = siglas.buscar_funcionario(nombre_archivo)
                except Exception:
                    datos = None
                if datos:
                    nombre, cargo = datos['nombre_completo'], datos['cargo']
                    departamento = datos['departamento']
                else:
                    nombre = nombre_archivo

                if dry_run:
                    self.stdout.write(f'  [dry-run] {bucket}/{obj["objeto"]} '
                                      f'-> ci={nombre_archivo} {nombre}')
                    continue

                archivo, creado = ArchivoCarnet.objects.get_or_create(
                    bucket=bucket, objeto=obj['objeto'],
                    defaults={'tipo': tipo, 'origen': ArchivoCarnet.Origen.HISTORICO})
                archivo.tipo = tipo
                archivo.origen = ArchivoCarnet.Origen.HISTORICO
                archivo.ci = nombre_archivo
                archivo.nombre = nombre
                archivo.cargo = cargo
                archivo.departamento = departamento
                archivo.tamano = obj['tamano']
                archivo.fecha_archivo = obj['fecha_archivo']
                archivo.save()
                if creado:
                    nuevos += 1
                else:
                    actualizados += 1
                marca = '+' if creado else '~'
                self.stdout.write(self.style.SUCCESS(
                    f'  {marca} {bucket}/{obj["objeto"]} '
                    f'(ci {nombre_archivo})'))

        accion = 'Indexados' if not dry_run else 'Encontrados (dry-run)'
        self.stdout.write(self.style.SUCCESS(
            f'{accion}: {total} | nuevos: {nuevos} | actualizados: '
            f'{actualizados} | sin cédula: {sin_ci}'))
