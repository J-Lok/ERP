from django import forms
from .models import Stock, StockTransaction, StockCategory
from django.core.exceptions import ValidationError
from accounts.utils import generate_company_code

class StockForm(forms.ModelForm):
    class Meta:
        model = Stock
        fields = ['item_code', 'name', 'category', 'description','image', 'quantity',
                  'unit', 'cost_price', 'selling_price', 'reorder_level', 'supplier',
                  'location', 'is_marketplace_visible', 'last_restocked']
        widgets = {
            'last_restocked': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
             'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
             'is_marketplace_visible': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
             'location': forms.TextInput(attrs={'list': 'location-suggestions', 'autocomplete': 'off'}),
             'item_code': forms.TextInput(attrs={'readonly': True}),
        }
        help_texts = {
            'item_code': 'Auto-generated from your company domain — cannot be edited.',
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)

        self.is_create = not (self.instance and self.instance.pk)
        self.fields['item_code'].required = False

        if self.company:
            # Filter categories to only those in the company
            self.fields['category'].queryset = StockCategory.objects.filter(company=self.company)

            from suppliers.models import Supplier
            self.fields['supplier'].queryset = Supplier.objects.filter(company=self.company, is_active=True).order_by('name')
            self.fields['supplier'].empty_label = '— No supplier assigned —'

            # Existing distinct locations for this company, offered via a
            # <datalist> on the location field — still free text (so a brand
            # new location can always be typed), but browsable like a select.
            self.location_suggestions = (
                Stock.objects
                .filter(company=self.company)
                .exclude(location='')
                .order_by('location')
                .values_list('location', flat=True)
                .distinct()
            )
            if self.is_create:
                self.fields['item_code'].initial = generate_company_code(self.company, Stock, 'item_code', 'ITM')
        else:
            self.location_suggestions = []

        # Make category and supplier non-required fields
        self.fields['category'].required = False
        self.fields['supplier'].required = False

    def clean(self):
        cleaned_data = super().clean()
        # item_code is read-only and server-generated — never trust a
        # client-submitted value. Regenerate on create; on edit it can never
        # change, so always fall back to the existing value.
        if self.company:
            if self.is_create:
                cleaned_data['item_code'] = generate_company_code(self.company, Stock, 'item_code', 'ITM')
            else:
                cleaned_data['item_code'] = self.instance.item_code
        return cleaned_data

class StockTransactionForm(forms.ModelForm):
    class Meta:
        model = StockTransaction
        fields = ['transaction_type', 'quantity', 'remarks']
        widgets = {
            'remarks': forms.Textarea(attrs={'rows': 3}),
        }
    
class StockCategoryForm(forms.ModelForm):
    class Meta:
        model = StockCategory
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Category name'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
    
    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if self.company:
            queryset = StockCategory.objects.filter(company=self.company, name=name)
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise ValidationError(f'Category "{name}" already exists in your company.')
        
        return name
    
    def save(self, commit=True):
        category = super().save(commit=False)
        if self.company:
            category.company = self.company
        
        if commit:
            category.save()
        
        return category  