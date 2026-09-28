from django.contrib import admin
from django.utils.html import format_html

from .models import Empleado


@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('numero_documento', 'nombre_completo', 'cargo', 'departamento',
                    'fecha_registro', 'foto_preview')
    list_filter = ('cargo', 'departamento')
    search_fields = ('numero_documento', 'nombres', 'apellidos', 'cargo')
    readonly_fields = ('fecha_registro', 'actualizado', 'foto_preview')
    fieldsets = (
        ('Datos del empleado', {
            'fields': ('numero_documento', 'nombres', 'apellidos', 'cargo', 'departamento'),
        }),
        ('Fotografía', {'fields': ('foto', 'foto_preview')}),
        ('Auditoría', {'fields': ('fecha_registro', 'actualizado')}),
    )

    @admin.display(description='Fotografía')
    def foto_preview(self, obj):
        if obj.foto:
            return format_html('<img src="{}" style="height:80px;border-radius:4px;" />', obj.foto.url)
        return '—'
