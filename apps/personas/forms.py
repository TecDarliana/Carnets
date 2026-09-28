from django import forms

from .models import Empleado


class EmpleadoForm(forms.ModelForm):
    class Meta:
        model = Empleado
        fields = ('numero_documento', 'nombres', 'apellidos', 'cargo', 'departamento', 'foto')
        widgets = {
            'numero_documento': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Ingrese el número de documento',
            }),
            'nombres': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre'}),
            'apellidos': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apellido'}),
            'cargo': forms.Select(attrs={'class': 'form-select'}),
            'departamento': forms.Select(attrs={'class': 'form-select'}),
            'foto': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }
