from django import forms

from apps.personas.models import Empleado

from .models import Carnet


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
