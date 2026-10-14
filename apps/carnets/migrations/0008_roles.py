"""Reemplaza los grupos antiguos por los roles Consultor, Analista y Gerente.

Los usuarios de cada grupo antiguo se mueven al rol equivalente:

- "Solo lectura"          → Consultor
- "Editores e impresión"  → Analista
- "Creadores manuales"    → Gerente

Los permisos de cada rol los fija la señal ``post_migrate`` de ``apps.carnets``.
"""

from django.db import migrations

MAPA_GRUPOS = {
    'Solo lectura': 'Consultor',
    'Editores e impresión': 'Analista',
    'Creadores manuales': 'Gerente',
}


def forwards(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for viejo, nuevo in MAPA_GRUPOS.items():
        try:
            grupo_viejo = Group.objects.get(name=viejo)
        except Group.DoesNotExist:
            continue
        grupo_nuevo, _ = Group.objects.get_or_create(name=nuevo)
        for user in grupo_viejo.user_set.all():
            grupo_nuevo.user_set.add(user)
        grupo_viejo.delete()


def backwards(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for viejo, nuevo in MAPA_GRUPOS.items():
        grupo_viejo, _ = Group.objects.get_or_create(name=viejo)
        try:
            grupo_nuevo = Group.objects.get(name=nuevo)
        except Group.DoesNotExist:
            continue
        for user in grupo_nuevo.user_set.all():
            grupo_viejo.user_set.add(user)
        grupo_nuevo.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('carnets', '0007_alter_credencial_options'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
