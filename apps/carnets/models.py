import base64
import uuid
import os
import shutil
from io import BytesIO

import qrcode
from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.conf import settings

from apps.personas.models import Empleado


class Plantilla(models.Model):
    class Meta:
        verbose_name = 'plantilla de carnet'
        verbose_name_plural = 'plantillas de carnet'
        ordering = ['-activa', 'nombre']

    nombre = models.CharField('nombre', max_length=100)
    descripcion = models.TextField('descripción', blank=True)
    archivo = models.FileField('archivo PPTX', upload_to='plantillas/', null=True, blank=True, default=None)
    razon_social = models.CharField('razón social / nombre jurídico', max_length=200, blank=True)
    telefono = models.CharField('teléfono', max_length=50, blank=True)
    correo = models.EmailField('correo', blank=True)
    activa = models.BooleanField('activa', default=False,
                                help_text='Marca la plantilla que se usará al generar carnets automáticamente')
    creado = models.DateTimeField('creado', auto_now_add=True)

    def __str__(self):
        return self.nombre


class Carnet(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        GENERADO = 'generado', 'Generado'

    class Tipo(models.TextChoices):
        EMPLEADO = 'empleado', 'Empleado'
        VISITANTE = 'visitante', 'Visitante'
        CONTRATISTA = 'contratista', 'Contratista'

    empleado = models.ForeignKey(
        Empleado, on_delete=models.CASCADE, related_name='carnets', verbose_name='empleado',
    )
    codigo = models.UUIDField('código único', default=uuid.uuid4, editable=False, unique=True)
    numero = models.CharField('número de carnet', max_length=30, unique=True, blank=True)
    tipo = models.CharField('tipo', max_length=15, choices=Tipo.choices, default=Tipo.EMPLEADO)
    fecha_emision = models.DateField('fecha de emisión', default=timezone.localdate)
    fecha_vencimiento = models.DateField('fecha de vencimiento', null=True, blank=True)
    estado = models.CharField('estado', max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    plantilla = models.CharField('plantilla / diseño', max_length=50, blank=True, default='default')
    observaciones = models.TextField('observaciones', blank=True)
    creado = models.DateTimeField('creado', auto_now_add=True)
    actualizado = models.DateTimeField('actualizado', auto_now=True)

    class Meta:
        verbose_name = 'carnet'
        verbose_name_plural = 'carnets'
        ordering = ['-creado']

    def __str__(self):
        return f'Carnet {self.numero} - {self.empleado.nombre_completo}'

    @property
    def esta_vigente(self):
        if self.estado != self.Estado.GENERADO:
            return False
        if self.fecha_vencimiento and self.fecha_vencimiento < timezone.localdate():
            return False
        return True

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = f'{self.empleado.numero_documento}-{timezone.now():%Y%m%d%H%M%S}'
        super().save(*args, **kwargs)

    @property
    def qr_imagen(self):
        contenido = (
            f'CARNET:{self.numero}\n'
            f'CODIGO:{self.codigo}\n'
            f'NOMBRE:{self.empleado.nombre_completo}\n'
            f'DOCUMENTO:{self.empleado.numero_documento}'
        )
        imagen = qrcode.make(contenido)
        buffer = BytesIO()
        imagen.save(buffer, format='PNG')
        return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode()

    def get_absolute_url(self):
        return reverse('carnets:detalle', args=[self.pk])


class Credencial(models.Model):
    """Carnet que puede provenir de SIGLAS o ser ingresado manualmente.

    A diferencia de `Carnet` (vinculado a Empleado), aquí los datos son
    editables antes de imprimir y el QR apunta a una página pública con la
    versión digital del carnet.
    """

    class Origen(models.TextChoices):
        SIGLAS = 'siglas', 'Base de datos (SIGLAS)'
        MANUAL = 'manual', 'Ingreso manual'

    nombre_completo = models.CharField('nombre completo', max_length=255)
    documento = models.CharField('documento (cédula / RIF)', max_length=32, blank=True)
    cargo = models.CharField('cargo', max_length=255, blank=True)
    foto = models.ImageField('foto', upload_to='fotos_carnets/', blank=True, null=True)
    codigo = models.UUIDField('código público (QR)', default=uuid.uuid4, editable=False, unique=True)
    origen = models.CharField('origen', max_length=10, choices=Origen.choices,
                              default=Origen.MANUAL, editable=False)
    ci_origen = models.CharField('cédula de origen (SIGLAS)', max_length=20, blank=True, editable=False)
    creado_por = models.ForeignKey(
        User, verbose_name='creado por', on_delete=models.SET_NULL, null=True, blank=True,
    )
    creado = models.DateTimeField('creado', auto_now_add=True)
    actualizado = models.DateTimeField('actualizado', auto_now=True)

    class Meta:
        verbose_name = 'credencial (carnet)'
        verbose_name_plural = 'credenciales / carnets'
        ordering = ['-creado']
        permissions = [
            ('ver_carnets', 'Puede consultar los datos de los carnets'),
            ('editar_imprimir_carnets', 'Puede editar la información e imprimir carnets'),
            ('crear_carnet_manual', 'Puede crear carnets con datos manuales'),
        ]

    def __str__(self):
        return f'{self.nombre_completo} ({self.documento or "sin documento"})'


class HistorialCarnet(models.Model):
    """Registro de cada carnet PDF generado por cédula (anverso + dorso)."""

    ci = models.CharField('cédula', max_length=20, db_index=True)
    nombre = models.CharField('nombre', max_length=200)
    cargo = models.CharField('cargo', max_length=150, blank=True)
    departamento = models.CharField('departamento', max_length=150, blank=True)
    usuario = models.ForeignKey(
        User, verbose_name='usuario', on_delete=models.SET_NULL, null=True, blank=True,
    )
    creado = models.DateTimeField('fecha de generación', auto_now_add=True)

    class Meta:
        verbose_name = 'carnet generado'
        verbose_name_plural = 'historial de carnets generados'
        ordering = ['-creado']

    def __str__(self):
        return f'{self.ci} - {self.nombre} ({self.creado:%d/%m/%Y %H:%M})'
