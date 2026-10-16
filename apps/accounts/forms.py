"""Formularios de administración de usuarios del sistema."""

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password

from apps.carnets.apps import GRUPOS

ROL_CHOICES = [(nombre, nombre) for nombre in GRUPOS]


def asignar_rol(user, nombre_rol):
    """Sustituye los grupos del usuario por el rol indicado (si existe)."""
    from django.contrib.auth.models import Group

    grupo = Group.objects.filter(name=nombre_rol).first()
    if grupo:
        user.groups.set([grupo])


class UsuarioCrearForm(forms.ModelForm):
    """Alta de usuario: datos, rol y contraseña inicial."""

    rol = forms.ChoiceField(label='Rol', choices=ROL_CHOICES,
                            widget=forms.Select(attrs={'class': 'form-select'}))
    password1 = forms.CharField(
        label='Contraseña', widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'is_active')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'Las contraseñas no coinciden.')
        elif p1:
            validate_password(p1)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
            asignar_rol(user, self.cleaned_data['rol'])
        return user


class UsuarioEditarForm(forms.ModelForm):
    """Edición de usuario: datos y rol (la contraseña va aparte)."""

    rol = forms.ChoiceField(label='Rol', choices=ROL_CHOICES,
                            widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'is_active')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        grupo = self.instance.groups.first()
        if grupo and grupo.name in GRUPOS:
            self.fields['rol'].initial = grupo.name

    def save(self, commit=True):
        user = super().save(commit)
        if commit:
            asignar_rol(user, self.cleaned_data['rol'])
        return user


class UsuarioPasswordForm(forms.Form):
    """Cambio de contraseña de un usuario por parte del administrador."""

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = user

    password1 = forms.CharField(
        label='Nueva contraseña', widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    password2 = forms.CharField(
        label='Confirmar nueva contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'Las contraseñas no coinciden.')
        elif p1:
            validate_password(p1, user=self.usuario)
        return cleaned
