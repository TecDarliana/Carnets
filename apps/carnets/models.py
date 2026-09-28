import base64
import uuid
from io import BytesIO

import qrcode
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.personas.models import Empleado


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
