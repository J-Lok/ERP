from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import check_password
from .models import User, Company


class CompanyCreationForm(forms.ModelForm):
    """
    Form for registering a new company along with its admin user.
    """
    # Admin user fields
    admin_first_name = forms.CharField(max_length=30, required=True)
    admin_last_name = forms.CharField(max_length=30, required=True)
    admin_email = forms.EmailField(required=True)
    admin_password = forms.CharField(
        widget=forms.PasswordInput,
        required=True,
        label="Admin Password"
    )
    confirm_admin_password = forms.CharField(
        widget=forms.PasswordInput,
        required=True,
        label="Confirm Admin Password"
    )

    # Company password fields (shared secret for team members)
    company_password = forms.CharField(
        widget=forms.PasswordInput,
        required=True,
        label="Company Password (shared with team)"
    )
    confirm_company_password = forms.CharField(
        widget=forms.PasswordInput,
        required=True,
        label="Confirm Company Password"
    )

    class Meta:
        model = Company
        fields = ['name', 'domain', 'contact_email', 'contact_phone', 'address']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_domain(self):
        domain = self.cleaned_data['domain'].lower().strip()
        if Company.objects.filter(domain=domain).exists():
            raise ValidationError('This domain is already taken.')
        return domain

    def clean(self):
        cleaned_data = super().clean()

        # Validate admin passwords
        admin_pw = cleaned_data.get('admin_password')
        confirm_admin = cleaned_data.get('confirm_admin_password')
        if admin_pw and confirm_admin and admin_pw != confirm_admin:
            self.add_error('confirm_admin_password', 'Admin passwords do not match.')

        # Validate company passwords
        company_pw = cleaned_data.get('company_password')
        confirm_company = cleaned_data.get('confirm_company_password')
        if company_pw and confirm_company and company_pw != confirm_company:
            self.add_error('confirm_company_password', 'Company passwords do not match.')

        # Check if admin email already exists
        admin_email = cleaned_data.get('admin_email')
        if admin_email and User.objects.filter(email=admin_email).exists():
            self.add_error('admin_email', 'This email is already registered.')

        return cleaned_data

    def save(self, commit=True):
        company = super().save(commit=False)
        # Hash the company password before saving
        company.set_company_password(self.cleaned_data['company_password'])

        if commit:
            company.save()
        return company


class UserRegistrationForm(UserCreationForm):
    """
    Form for a new user to join an existing company using the company's domain and shared password.
    """
    company_domain = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'placeholder': 'company-domain'}),
        help_text="Enter your company's domain"
    )
    company_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Company password'}),
        help_text="Enter your company's shared password"
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'role']

    def clean(self):
        cleaned_data = super().clean()
        domain = cleaned_data.get('company_domain')
        company_pw = cleaned_data.get('company_password')

        if domain and company_pw:
            try:
                company = Company.objects.get(domain=domain)
                if not company.check_company_password(company_pw):
                    raise ValidationError('Invalid company password.')
                # Store company in cleaned_data for use in save()
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
    """
    Custom login form that requires company domain in addition to email and password.
    """
    company_domain = forms.CharField(max_length=200, required=True)

    def clean(self):
        # First, call the parent clean to get username and password
        cleaned_data = super().clean()
        domain = cleaned_data.get('company_domain')
        username = cleaned_data.get('username')  # This is the email field
        password = cleaned_data.get('password')

        if domain and username and password:
            try:
                company = Company.objects.get(domain=domain)
                # Check if a user with this email exists under this company
                try:
                    user = User.objects.get(email=username, company=company)
                except User.DoesNotExist:
                    raise ValidationError('No account found with these credentials.')

                # Authenticate with the provided password
                user = authenticate(email=username, password=password)
                if user is None:
                    raise ValidationError('Invalid email or password.')

                # Attach the user and company to cleaned_data for the view
                cleaned_data['user'] = user
                cleaned_data['company'] = company

            except Company.DoesNotExist:
                raise ValidationError('Company with this domain does not exist.')

        return cleaned_data


class UserProfileForm(forms.ModelForm):
    """Form for users to edit their own profile."""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'department', 'position']
        widgets = {
            'email': forms.EmailInput(attrs={'readonly': 'readonly'}),  # Email should not be changed
        }

    def clean_email(self):
        # Prevent changing email (optional)
        return self.instance.email


class UserManagementForm(forms.ModelForm):
    """Form for admin users to manage company user roles."""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'department', 'position', 'role']
        widgets = {
            'email': forms.EmailInput(attrs={'readonly': 'readonly'}),
        }

    def clean_email(self):
        return self.instance.email


class CompanyProfileForm(forms.ModelForm):
    """Form for company admins to edit company details."""
    class Meta:
        model = Company
        fields = ['name', 'domain', 'contact_email', 'contact_phone', 'address',
                  'subscription_plan', 'is_active']
        widgets = {
            'domain': forms.TextInput(attrs={'readonly': 'readonly'}),  # Domain shouldn't be changed casually
        }


class CompanyPasswordChangeForm(forms.Form):
    """
    Form for company admins to change the company's shared password.
    """
    current_company_password = forms.CharField(
        widget=forms.PasswordInput,
        label="Current Company Password"
    )
    new_company_password = forms.CharField(
        widget=forms.PasswordInput,
        label="New Company Password"
    )
    confirm_new_company_password = forms.CharField(
        widget=forms.PasswordInput,
        label="Confirm New Company Password"
    )

    def __init__(self, company, *args, **kwargs):
        self.company = company
        super().__init__(*args, **kwargs)

    def clean_current_company_password(self):
        current = self.cleaned_data['current_company_password']
        if not self.company.check_company_password(current):
            raise ValidationError("Current company password is incorrect.")
        return current

    def clean(self):
        cleaned_data = super().clean()
        new_pw = cleaned_data.get('new_company_password')
        confirm = cleaned_data.get('confirm_new_company_password')
        if new_pw and confirm and new_pw != confirm:
            self.add_error('confirm_new_company_password', "New passwords do not match.")
        return cleaned_data

    def save(self):
        new_pw = self.cleaned_data['new_company_password']
        self.company.set_company_password(new_pw)
        self.company.save(update_fields=['company_password'])