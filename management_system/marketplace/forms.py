from django import forms
from django.core.exceptions import ValidationError
from .models import Client, Order
from accounts.models import Company

class ClientRegistrationForm(forms.ModelForm):
    company_domain = forms.CharField(
        max_length=200,
        help_text="Enter the company domain you want to shop from"
    )
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")
    
    class Meta:
        model = Client
        fields = ['first_name', 'last_name', 'email', 'phone', 'address', 'city', 'country', 'postal_code']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        company_domain = cleaned_data.get('company_domain')
        
        # Check passwords match
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', 'Passwords do not match.')
        
        # Verify company exists
        if company_domain:
            try:
                company = Company.objects.get(domain=company_domain, is_active=True)
                cleaned_data['company'] = company
            except Company.DoesNotExist:
                self.add_error('company_domain', 'Company with this domain does not exist.')
        
        # Check if email already exists for this company
        email = cleaned_data.get('email')
        if email and company_domain:
            if Client.objects.filter(company__domain=company_domain, email=email).exists():
                self.add_error('email', 'An account with this email already exists.')
        
        return cleaned_data
    
    def save(self, commit=True):
        client = super().save(commit=False)
        client.company = self.cleaned_data['company']
        client.set_password(self.cleaned_data['password'])
        
        if commit:
            client.save()
            # Create cart and wishlist for client
            from .models import Cart, Wishlist
            Cart.objects.create(client=client)
            Wishlist.objects.create(client=client)
        
        return client


class ClientLoginForm(forms.Form):
    company_domain = forms.CharField(max_length=200)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    
    def clean(self):
        cleaned_data = super().clean()
        company_domain = cleaned_data.get('company_domain')
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')
        
        if company_domain and email and password:
            try:
                company = Company.objects.get(domain=company_domain, is_active=True)
                
                try:
                    client = Client.objects.get(company=company, email=email, is_active=True)
                    
                    if not client.check_password(password):
                        raise ValidationError('Invalid email or password.')
                    
                    cleaned_data['client'] = client
                    
                except Client.DoesNotExist:
                    raise ValidationError('No account found with these credentials.')
                    
            except Company.DoesNotExist:
                raise ValidationError('Company with this domain does not exist.')
        
        return cleaned_data


class ClientProfileForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['first_name', 'last_name', 'phone', 'address', 'city', 'country', 'postal_code']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }


class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['shipping_address', 'shipping_city', 'shipping_country', 'shipping_postal_code', 'notes']
        widgets = {
            'shipping_address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'shipping_city': forms.TextInput(attrs={'class': 'form-control'}),
            'shipping_country': forms.TextInput(attrs={'class': 'form-control'}),
            'shipping_postal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Any special instructions?'}),
        }


class AddToCartForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, initial=1)