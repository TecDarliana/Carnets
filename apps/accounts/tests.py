from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

CLAVE = 'Clave-Test-123'


class BaseUsuarios(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser('root', password=CLAVE)
        cls.gerente = User.objects.create_user('gerente', password=CLAVE)
        cls.analista = User.objects.create_user('analista', password=CLAVE)
        cls.consultor = User.objects.create_user('consultor', password=CLAVE)
        cls.objetivo = User.objects.create_user('objetivo', password=CLAVE)
        Group.objects.get_or_create(name='Gerente')
        Group.objects.get_or_create(name='Analista')
        Group.objects.get_or_create(name='Consultor')
        cls.gerente.groups.add(Group.objects.get(name='Gerente'))
        cls.consultor.groups.add(Group.objects.get(name='Consultor'))

    def login(self, username):
        self.assertTrue(self.client.login(username=username, password=CLAVE))


class AccesoTests(BaseUsuarios):
    def test_anonimo_redirige_a_login(self):
        respuesta = self.client.get(reverse('accounts:usuario_lista'))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('login', respuesta['Location'])

    def test_consultor_sin_permiso_recibe_403(self):
        self.login('consultor')
        for url in ('accounts:usuario_lista', 'accounts:usuario_crear'):
            respuesta = self.client.get(reverse(url))
            self.assertEqual(respuesta.status_code, 403, url)

    def test_consultor_no_puede_cambiar_password(self):
        self.login('consultor')
        respuesta = self.client.post(
            reverse('accounts:usuario_password', args=[self.objetivo.pk]),
            {'password1': CLAVE, 'password2': CLAVE})
        self.assertEqual(respuesta.status_code, 403)

    def test_gerente_ve_listado(self):
        self.login('gerente')
        respuesta = self.client.get(reverse('accounts:usuario_lista'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'objetivo')

    def test_superuser_ve_listado(self):
        self.login('root')
        respuesta = self.client.get(reverse('accounts:usuario_lista'))
        self.assertEqual(respuesta.status_code, 200)


class AdministrarUsuariosTests(BaseUsuarios):
    def gerente_crea_usuario(self):
        self.login('gerente')
        respuesta = self.client.post(reverse('accounts:usuario_crear'), {
            'username': 'nuevo', 'first_name': 'Nuevo', 'last_name': 'Uno',
            'email': 'nuevo@test.com', 'rol': 'Analista', 'is_active': 'on',
            'password1': CLAVE, 'password2': CLAVE,
        })
        return respuesta

    def test_gerente_crea_usuario_con_rol(self):
        respuesta = self.gerente_crea_usuario()
        self.assertRedirects(respuesta, reverse('accounts:usuario_lista'))
        nuevo = User.objects.get(username='nuevo')
        self.assertEqual(list(nuevo.groups.values_list('name', flat=True)), ['Analista'])
        self.assertTrue(self.client.login(username='nuevo', password=CLAVE))

    def test_gerente_edita_usuario(self):
        self.login('gerente')
        respuesta = self.client.post(
            reverse('accounts:usuario_editar', args=[self.objetivo.pk]),
            {'first_name': 'Nombre', 'last_name': 'Nuevo', 'email': 'x@test.com',
             'rol': 'Consultor', 'is_active': 'on'})
        self.assertRedirects(respuesta, reverse('accounts:usuario_lista'))
        self.objetivo.refresh_from_db()
        self.assertEqual(self.objetivo.first_name, 'Nombre')
        self.assertEqual(list(self.objetivo.groups.values_list('name', flat=True)),
                         ['Consultor'])

    def test_gerente_cambia_password(self):
        self.login('gerente')
        respuesta = self.client.post(
            reverse('accounts:usuario_password', args=[self.objetivo.pk]),
            {'password1': 'Otra-Clave-456', 'password2': 'Otra-Clave-456'})
        self.assertRedirects(respuesta, reverse('accounts:usuario_lista'))
        self.assertTrue(self.client.login(username='objetivo', password='Otra-Clave-456'))

    def test_gerente_no_toca_superusuarios(self):
        self.login('gerente')
        for url in ('accounts:usuario_editar', 'accounts:usuario_password'):
            respuesta = self.client.get(reverse(url, args=[self.superuser.pk]))
            self.assertEqual(respuesta.status_code, 403, url)
        respuesta = self.client.post(reverse('accounts:usuario_toggle',
                                             args=[self.superuser.pk]))
        self.assertEqual(respuesta.status_code, 403)

    def test_nadie_se_desactiva_a_si_mismo(self):
        self.login('gerente')
        respuesta = self.client.post(reverse('accounts:usuario_toggle',
                                             args=[self.gerente.pk]))
        self.assertRedirects(respuesta, reverse('accounts:usuario_lista'))
        self.gerente.refresh_from_db()
        self.assertTrue(self.gerente.is_active)

    def test_gerente_desactiva_y_activa_usuario(self):
        self.login('gerente')
        self.client.post(reverse('accounts:usuario_toggle', args=[self.objetivo.pk]))
        self.objetivo.refresh_from_db()
        self.assertFalse(self.objetivo.is_active)
        self.client.post(reverse('accounts:usuario_toggle', args=[self.objetivo.pk]))
        self.objetivo.refresh_from_db()
        self.assertTrue(self.objetivo.is_active)

    def test_superuser_puede_editar_superusuarios(self):
        otro_admin = User.objects.create_superuser('root2', password=CLAVE)
        self.login('root')
        respuesta = self.client.get(
            reverse('accounts:usuario_editar', args=[otro_admin.pk]))
        self.assertEqual(respuesta.status_code, 200)


class HistorialSoloLecturaTests(BaseUsuarios):
    def test_no_existe_url_de_eliminacion(self):
        self.login('root')
        respuesta = self.client.post('/carnets/historial/1/eliminar/')
        self.assertEqual(respuesta.status_code, 404)
