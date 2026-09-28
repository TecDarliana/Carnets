from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse


class Empleado(models.Model):
    class Cargo(models.TextChoices):
        ASISTENTE_ADMINISTRATIVO = 'ASISTENTE ADMINISTRATIVO', 'Asistente Administrativo'
        SECRETARIA = 'SECRETARIA', 'Secretaria'
        DIRECTOR = 'DIRECTOR', 'Director(a)'
        ANALISTA = 'ANALISTA', 'Analista'
        TECNICO = 'TECNICO', 'Técnico(a)'
        GUARDIA = 'GUARDIA', 'Guardia'
        MENSAJERO = 'MENSAJERO', 'Mensajero'
        OTRO = 'OTRO', 'Otro'

    class Departamento(models.TextChoices):
        DIRECCION_ADMINISTRACION = 'DIRECCION DE ADMINISTRACION', 'Dirección de Administración'
        DIRECCION_OFICINAS_REGIONALES = (
            'DIRECCION GENERAL DE OFICINAS REGIONALES',
            'Dirección General de Oficinas Regionales',
        )
        RECURSOS_HUMANOS = 'RECURSOS HUMANOS', 'Recursos Humanos'
        CONTABILIDAD = 'CONTABILIDAD', 'Contabilidad'
        INFORMATICA = 'INFORMATICA', 'Informática'
        OPERACIONES = 'OPERACIONES', 'Operaciones'
        OTRO = 'OTRO', 'Otro'

    numero_documento = models.CharField(
        'número de documento', max_length=30, unique=True,
        validators=[RegexValidator(r'^[A-Za-z0-9\-]+$', 'Solo letras, números y guiones.')],
    )
    nombres = models.CharField('nombre', max_length=100)
    apellidos = models.CharField('apellido', max_length=100)
    cargo = models.CharField('cargo', max_length=100, choices=Cargo.choices)
    departamento = models.CharField('departamento', max_length=100, choices=Departamento.choices)
    foto = models.ImageField('fotografía', upload_to='fotos/', null=True, blank=False)

    fecha_registro = models.DateTimeField('fecha de registro', auto_now_add=True)
    actualizado = models.DateTimeField('actualizado', auto_now=True)

    class Meta:
        verbose_name = 'empleado'
        verbose_name_plural = 'empleados'
        ordering = ['apellidos', 'nombres']

    def __str__(self):
        return f'{self.apellidos}, {self.nombres} ({self.numero_documento})'

    @property
    def nombre_completo(self):
        return f'{self.nombres} {self.apellidos}'.strip()

    def get_absolute_url(self):
        return reverse('personas:detalle', args=[self.pk])
