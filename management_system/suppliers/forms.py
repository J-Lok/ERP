from django import forms
from django.core.exceptions import ValidationError

from .models import Supplier


class SupplierForm(forms.ModelForm):
    """Create or edit a supplier. Pass ``company=<Company>`` as a kwarg."""

    class Meta:
        model = Supplier
        fields = ['name', 'contact_person', 'email', 'phone', 'address', 'notes', 'is_active']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, company=None, **kwargs):
        self.company = company
        super().__init__(*args, **kwargs)
        self.fields['contact_person'].required = False
        self.fields['email'].required = False
        self.fields['phone'].required = False
        self.fields['address'].required = False
        self.fields['notes'].required = False

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if self.company:
            qs = Supplier.objects.filter(company=self.company, name__iexact=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(f'Supplier "{name}" already exists in your company.')
        return name

    def save(self, commit=True):
        supplier = super().save(commit=False)
        if self.company:
            supplier.company = self.company
        if commit:
            supplier.save()
        return supplier
