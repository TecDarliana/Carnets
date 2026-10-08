from django.apps import AppConfig
from django.db.models.signals import post_migrate

GRUPOS = {
    'Solo lectura': {
        'codenames': ['ver_carnets'],
        'descripcion': 'Solo consulta los datos de los carnets.',
    },
    'Editores e impresión': {
        'codenames': ['ver_carnets', 'editar_imprimir_carnets'],
        'descripcion': 'Puede editar la información del carnet e imprimirlo.',
    },
    'Creadores manuales': {
        'codenames': ['ver_carnets', 'crear_carnet_manual'],
        'descripcion': 'Puede crear carnets con información manual (no proviene de la base de datos).',
    },
}


def crear_grupos(sender, **kwargs):
    """Crea (si no existen) los grupos de permisos de carnets. Idempotente."""
    from django.contrib.auth.models import Group, Permission

    try:
        codenames = {
            'ver_carnets', 'editar_imprimir_carnets', 'crear_carnet_manual',
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
