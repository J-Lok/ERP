from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from .models import User, Company
from django.contrib.auth.hashers import check_password

class CompanyCreationForm(forms.ModelForm):
    admin_first_name = forms.CharField(max_length=30, required=True)
    admin_last_name = forms.CharField(max_length=30, required=True)
    admin_email = forms.EmailField(required=True)
    admin_password = forms.CharField(widget=forms.PasswordInput, required=True)
    confirm_admin_password = forms.CharField(widget=forms.PasswordInput, required=True)
    
    class Meta:
        model = Company
        fields = ['name', 'domain', 'company_password', 'contact_email', 'contact_phone', 'address']
        widgets = {
            'company_password': forms.PasswordInput(),
            'address': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean_domain(self):
        domain = self.cleaned_data['domain'].lower().strip()
        if Company.objects.filter(domain=domain).exists():
            raise ValidationError('This domain is already taken.')
        return domain
    
    def clean(self):
        cleaned_data = super().clean()

        # Check admin passwords match
        admin_password = cleaned_data.get('admin_password')
        confirm_admin_password = cleaned_data.get('confirm_admin_password')
        
        if admin_password and confirm_admin_password and admin_password != confirm_admin_password:
            self.add_error('confirm_admin_password', 'Admin passwords do not match.')
        
        # Check if admin email already exists
        admin_email = cleaned_data.get('admin_email')
        if admin_email and User.objects.filter(email=admin_email).exists():
            self.add_error('admin_email', 'This email is already registered.')
        
        return cleaned_data
    
    def save(self, commit=True):
        company = super().save(commit=False)
        
        # Set company password
        company.set_company_password(self.cleaned_data['company_password'])

        if commit:
            company.save()
        
        return company

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'department', 'position']

class CompanyProfileForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['name', 'domain', 'contact_email', 'contact_phone', 'address', 'subscription_plan', 'is_active']
class UserRegistrationForm(UserCreationForm):
    company_domain = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'placeholder': 'company-domain'}),
        help_text="Enter your company domain"
    )
    company_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Company password'}),
        help_text="Enter your company's shared password"
    )
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'password1', 'password2', 'phone']
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Last Name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Email Address'}),
            'phone': forms.TextInput(attrs={'placeholder': 'Phone Number'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        company_domain = cleaned_data.get('company_domain')
        company_password = cleaned_data.get('company_password')
        
        if company_domain and company_password:
            try:
                company = Company.objects.get(domain=company_domain)
                if not check_password(company_password, company.company_password):
                    raise ValidationError('Invalid company password.')
                cleaned_data['company'] = company
            except Company.DoesNotExist:
                raise ValidationError('Company with this domain does not exist.')
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        company = self.cleaned_data.get('company')
        if company:
            user.company = company
        if commit:
            user.save()
        return user

class CompanyLoginForm(AuthenticationForm):
    company_domain = forms.CharField(max_length=200)

    def clean(self):
        cleaned_data = super().clean()

        company_domain = cleaned_data.get('company_domain')
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')

        if company_domain and username and password:
            try:
                company = Company.objects.get(domain=company_domain)

                try:
                    User.objects.get(email=username, company=company)
                except User.DoesNotExist:
                    raise ValidationError('No account found with these credentials.')

                user = authenticate(email=username, password=password)
                if user is None:
                    raise ValidationError('Invalid email or password.')

                user.backend = 'django.contrib.auth.backends.ModelBackend'
                cleaned_data['user'] = user

            except Company.DoesNotExist:
                raise ValidationError('Company with this domain does not exist.')

        return cleaned_data
