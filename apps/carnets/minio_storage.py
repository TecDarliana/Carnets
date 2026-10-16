"""Resguardo de carnets y fotos en el almacenamiento de objetos MinIO.

Todos los accesos son de "mejor esfuerzo": si MinIO no está disponible, se
registra el error y la aplicación sigue funcionando con normalidad. Solo el
comando de importación histórica (`carnets_importar_historico`) reporta los
fallos, porque ahí el resguardo es el objetivo principal.

Convenciones de nombres (compatibles con el sistema anterior):
- Carnet PDF de un funcionario:  ``Carnet_<ci>.pdf``
- Fotografía de un funcionario:  ``<ci>.jpg``
- Lote de carnets (Generar Todos): ``lotes/Carnets_lote_<fecha>.pdf``
- Importación histórica:        ``historico/...`` (subido por réplica externa)
"""

import logging
import re
from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

CI_RE = re.compile(r'(?:V)?(\d{5,12})', re.IGNORECASE)


def _config():
    cfg = getattr(settings, 'MINIO', None) or {}
    if not cfg.get('ACCESS_KEY') or not cfg.get('SECRET_KEY'):
        return None
    return cfg


def cliente():
    """Cliente S3 de MinIO o None si no hay credenciales configuradas."""
    cfg = _config()
    if cfg is None:
        return None
    return boto3.client(
        's3',
        endpoint_url=cfg['ENDPOINT_URL'],
        aws_access_key_id=cfg['ACCESS_KEY'],
        aws_secret_access_key=cfg['SECRET_KEY'],
        config=Config(signature_version='s3v4', connect_timeout=5,
                      retries={'max_attempts': 1}),
        region_name='us-east-1',
    )


def ci_de_nombre(nombre):
    """Extrae la cédula de un nombre de archivo (ej. Carnet_V12345678.pdf)."""
    m = CI_RE.search(Path(nombre).stem)
    return m.group(1) if m else ''


def asegurar_buckets():
    """Crea los buckets de resguardo si no existen (best-effort)."""
    s3 = cliente()
    if s3 is None:
        return False
    cfg = settings.MINIO
    for bucket in (cfg['BUCKET_CARNETS'], cfg['BUCKET_FOTOS']):
        try:
            s3.create_bucket(Bucket=bucket)
        except ClientError as exc:
            # BucketAlreadyOwnedByYou: ya existe, no es un error.
            codigo = exc.response.get('Error', {}).get('Code', '')
            if codigo not in ('BucketAlreadyOwnedByYou', 'BucketAlreadyExists'):
                logger.warning('No se pudo crear/verificar el bucket %s: %s',
                               bucket, exc)
        except BotoCoreError as exc:
            logger.warning('No se pudo conectar a MinIO para el bucket %s: %s',
                           bucket, exc)
            return False
    return True


def _catalogar(bucket, objeto, tipo, origen, ci='', nombre='', cargo='',
               departamento='', tamano=0, fecha_archivo=None):
    """Registra (o actualiza) el objeto en el catálogo local `ArchivoCarnet`."""
    from .models import ArchivoCarnet

    archivo, _ = ArchivoCarnet.objects.get_or_create(
        bucket=bucket, objeto=objeto,
        defaults={'tipo': tipo, 'origen': origen})
    archivo.tipo = tipo
    archivo.origen = origen
    archivo.ci = ci
    archivo.nombre = nombre
    archivo.cargo = cargo
    archivo.departamento = departamento
    archivo.tamano = tamano
    archivo.fecha_archivo = fecha_archivo
    archivo.save()
    return archivo


def _guardar(bucket, objeto, contenido, tipo, **catalogo):
    """Sube el objeto y lo cataloga. Devuelve True si se guardó."""
    s3 = cliente()
    if s3 is None:
        return False
    try:
        s3.put_object(Bucket=bucket, Key=objeto, Body=contenido)
    except (ClientError, BotoCoreError) as exc:
        logger.warning('No se pudo resguardar %s/%s: %s', bucket, objeto, exc)
        return False
    _catalogar(bucket, objeto, tipo, fecha_archivo=timezone.now(),
               tamano=len(contenido), **catalogo)
    return True


def guardar_pdf_carnet(ci, nombre, cargo='', departamento='', pdf=None):
    """Resguarda el PDF del carnet de un funcionario (Carnet_<ci>.pdf)."""
    cfg = settings.MINIO
    return _guardar(
        cfg['BUCKET_CARNETS'], f'Carnet_{ci}.pdf', pdf, 'carnet',
        origen='generado', ci=ci, nombre=nombre, cargo=cargo,
        departamento=departamento)


def guardar_pdf_lote(pdf, cantidad):
    """Resguarda el PDF conjunto del botón Generar Todos."""
    cfg = settings.MINIO
    ahora = timezone.localtime()
    objeto = 'lotes/Carnets_lote_%s.pdf' % ahora.strftime('%Y%m%d_%H%M%S')
    return _guardar(
        cfg['BUCKET_CARNETS'], objeto, pdf, 'lote', origen='generado',
        nombre='Lote de %d carnet(s) - %s' % (cantidad, ahora.strftime('%d/%m/%Y')),
        tamano=len(pdf), fecha_archivo=ahora)


def guardar_foto(ci, foto):
    """Resguarda la fotografía original del funcionario (<ci>.jpg)."""
    cfg = settings.MINIO
    return _guardar(cfg['BUCKET_FOTOS'], f'{ci}.jpg', foto, 'foto',
                    origen='generado', ci=ci)


def descargar(bucket, objeto):
    """Bytes del objeto o None si no está disponible."""
    s3 = cliente()
    if s3 is None:
        return None
    try:
        resp = s3.get_object(Bucket=bucket, Key=objeto)
        return resp['Body'].read()
    except (ClientError, BotoCoreError) as exc:
        logger.warning('No se pudo descargar %s/%s: %s', bucket, objeto, exc)
        return None


def listar(bucket, prefijo=''):
    """Itera los objetos de un bucket (yield de dicts con key, tamaño, fecha)."""
    s3 = cliente()
    if s3 is None:
        return
    token = None
    while True:
        kwargs = {'Bucket': bucket, 'Prefix': prefijo}
        if token:
            kwargs['ContinuationToken'] = token
        try:
            resp = s3.list_objects_v2(**kwargs)
        except (ClientError, BotoCoreError) as exc:
            logger.warning('No se pudo listar %s/%s: %s', bucket, prefijo, exc)
            return
        for obj in resp.get('Contents', []):
            yield {
                'objeto': obj['Key'],
                'tamano': obj.get('Size', 0),
                'fecha_archivo': obj.get('LastModified'),
            }
        if not resp.get('IsTruncated'):
            return
        token = resp.get('NextContinuationToken')
