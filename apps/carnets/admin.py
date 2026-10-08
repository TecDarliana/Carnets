from django.contrib import admin
from django.utils.html import format_html

from .models import Carnet, Credencial, HistorialCarnet


@admin.register(Carnet)
class CarnetAdmin(admin.ModelAdmin):
    list_display = ('numero', 'empleado', 'tipo', 'fecha_emision',
                    'fecha_vencimiento', 'estado', 'vigente')
    list_filter = ('estado', 'tipo', 'fecha_emision')
    search_fields = ('numero', 'empleado__nombres', 'empleado__apellidos',
                     'empleado__numero_documento')
    readonly_fields = ('codigo', 'creado', 'actualizado')
    autocomplete_fields = ('empleado',)

    @admin.display(boolean=True, description='¿Vigente?')
    def vigente(self, obj):
        return obj.esta_vigente


@admin.register(HistorialCarnet)
class HistorialCarnetAdmin(admin.ModelAdmin):
    list_display = ('ci', 'nombre', 'cargo', 'usuario', 'creado')
    search_fields = ('ci', 'nombre')
    list_filter = ('creado',)
    date_hierarchy = 'creado'
    readonly_fields = ('ci', 'nombre', 'cargo', 'departamento', 'usuario', 'creado')


@admin.register(Credencial)
class CredencialAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'documento', 'cargo', 'origen',
                    'creado_por', 'creado')
    list_filter = ('origen', 'creado')
    search_fields = ('nombre_completo', 'documento', 'cargo')
    readonly_fields = ('origen', 'ci_origen', 'codigo', 'creado_por',
                       'creado', 'actualizado')
