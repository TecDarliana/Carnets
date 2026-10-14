from django.apps import AppConfig
from django.db.models.signals import post_migrate

GRUPOS = {
    'Consultor': {
        'codenames': ['ver_carnets'],
        'descripcion': 'Solo consulta: busca por cédula, ve el carnet y el historial.',
    },
    'Analista': {
        'codenames': ['ver_carnets', 'editar_imprimir_carnets'],
        'descripcion': 'Genera carnets de empleados existentes en la base de datos '
                       '(no puede crear carnets especiales).',
    },
    'Gerente': {
        'codenames': ['ver_carnets', 'editar_imprimir_carnets',
                      'crear_carnet_manual', 'editar_plantillas'],
        'descripcion': 'Acceso total: todo tipo de carnets, plantillas, '
                       'búsqueda, historial y empleados.',
    },
}


def crear_grupos(sender, **kwargs):
    """Crea (si no existen) los grupos de permisos de carnets. Idempotente."""
    from django.contrib.auth.models import Group, Permission

    try:
        codenames = {
            'ver_carnets', 'editar_imprimir_carnets', 'crear_carnet_manual',
            'editar_plantillas',
        }
        permisos_codenames = {
            p.codename: p for p in Permission.objects.filter(codename__in=codenames)
        }
        for nombre, cfg in GRUPOS.items():
            grupo, _ = Group.objects.get_or_create(name=nombre)
            requeridos = [permisos_codenames[c] for c in cfg['codenames']
                          if c in permisos_codenames]
            grupo.permissions.set(requeridos)
    except Exception:
        # Aún no hay tablas/permisos migrados; no bloquear el arranque.
        pass


class CarnetsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.carnets'
    verbose_name = 'Carnets'

    def ready(self):
        post_migrate.connect(crear_grupos, sender=self)
