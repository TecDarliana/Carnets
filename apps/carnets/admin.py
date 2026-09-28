from django.contrib import admin
from django.utils.html import format_html

from .models import Carnet


@admin.register(Carnet)
class CarnetAdmin(admin.ModelAdmin):
    list_display = ('numero', 'empleado', 'tipo', 'fecha_emision',
                    'fecha_vencimiento', 'estado', 'vigente')
    list_filter = ('estado', 'tipo', 'fecha_emision')
    search_fields = ('numero', 'empleado__nombres', 'empleado__apellidos',
                     'empleado__codigo_empleado')
    readonly_fields = ('codigo', 'creado', 'actualizado')
    autocomplete_fields = ('empleado',)

    @admin.display(boolean=True, description='¿Vigente?')
    def vigente(self, obj):
        return obj.esta_vigente
