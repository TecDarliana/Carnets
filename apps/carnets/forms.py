from django import forms

from apps.personas.models import Empleado

from .models import Carnet, Credencial, Plantilla


class CredencialForm(forms.ModelForm):
    """Datos del carnet: editables antes de imprimir."""

    class Meta:
        model = Credencial
        fields = ('nombre_completo', 'documento', 'cargo', 'foto')
        widgets = {
            'nombre_completo': forms.TextInput(attrs={'class': 'form-control'}),
            'documento': forms.TextInput(attrs={'class': 'form-control',
                                                'inputmode': 'numeric'}),
            'cargo': forms.TextInput(attrs={'class': 'form-control'}),
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


class CarnetForm(forms.ModelForm):
    class Meta:
        model = Carnet
        fields = ('empleado', 'tipo', 'fecha_vencimiento', 'observaciones')
        widgets = {
            'empleado': forms.Select(attrs={'class': 'form-select'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'fecha_vencimiento': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'},
            ),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['empleado'].queryset = Empleado.objects.all()
        self.fields['fecha_vencimiento'].required = False
        self.fields['observaciones'].required = False
