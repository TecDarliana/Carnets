from django import forms

from .models import Credencial, Plantilla


class CredencialForm(forms.ModelForm):
    """Datos del carnet: editables antes de imprimir."""

    class Meta:
        model = Credencial
        fields = ('nombre_completo', 'documento', 'cargo',
                  'fecha_vencimiento', 'foto')
        widgets = {
            'nombre_completo': forms.TextInput(attrs={'class': 'form-control'}),
            'documento': forms.TextInput(attrs={'class': 'form-control',
                                                'inputmode': 'numeric'}),
            'cargo': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_vencimiento': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'},
            ),
            'foto': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class PlantillaForm(forms.ModelForm):
    class Meta:
        model = Plantilla
        fields = ('nombre', 'descripcion', 'razon_social', 'telefono', 'correo',
                  'archivo', 'activa')
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'razon_social': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'correo': forms.EmailInput(attrs={'class': 'form-control'}),
            'archivo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
