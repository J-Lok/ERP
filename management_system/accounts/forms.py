from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError

from .models import User, Company


# ---------------------------------------------------------------------------
# Shared widget defaults
# ---------------------------------------------------------------------------

_PASSWORD_WIDGET = forms.PasswordInput(attrs={'autocomplete': 'new-password'})
_CURRENT_PASSWORD_WIDGET = forms.PasswordInput(attrs={'autocomplete': 'current-password'})


# ---------------------------------------------------------------------------
# Company registration
# ---------------------------------------------------------------------------

class CompanyCreationForm(forms.ModelForm):
    """Register a new company and its initial admin user in one step."""

    # Admin user fields
    admin_first_name = forms.CharField(max_length=30)
    admin_last_name = forms.CharField(max_length=30)
    admin_email = forms.EmailField()
    admin_password = forms.CharField(
        widget=_PASSWORD_WIDGET,
        label='Admin Password',
        min_length=8,
    )
    confirm_admin_password = forms.CharField(
        widget=_PASSWORD_WIDGET,
        label='Confirm Admin Password',
    )

    # Company shared-secret fields
    company_password = forms.CharField(
        widget=_PASSWORD_WIDGET,
        label='Company Password (shared with team)',
        min_length=8,
    )
    confirm_company_password = forms.CharField(
        widget=_PASSWORD_WIDGET,
        label='Confirm Company Password',
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

    def clean_admin_email(self):
        email = self.cleaned_data['admin_email'].lower().strip()
        if User.objects.filter(email=email).exists():
            raise ValidationError('This email is already registered.')
        return email

    def clean(self):
        cleaned_data = super().clean()

        admin_pw = cleaned_data.get('admin_password')
        confirm_admin = cleaned_data.get('confirm_admin_password')
        if admin_pw and confirm_admin and admin_pw != confirm_admin:
            self.add_error('confirm_admin_password', 'Admin passwords do not match.')

        company_pw = cleaned_data.get('company_password')
        confirm_company = cleaned_data.get('confirm_company_password')
        if company_pw and confirm_company and company_pw != confirm_company:
            self.add_error('confirm_company_password', 'Company passwords do not match.')

        return cleaned_data

    def save(self, commit=True):
        company = super().save(commit=False)
        company.set_company_password(self.cleaned_data['company_password'])
        if commit:
            company.save()
        return company


# ---------------------------------------------------------------------------
# User registration (join existing company)
# ---------------------------------------------------------------------------

class UserRegistrationForm(UserCreationForm):
    """Allow a new user to join an existing company via domain + shared password."""

    company_domain = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'placeholder': 'your-company-domain'}),
        help_text="Your company's domain (ask your administrator).",
    )
    company_password = forms.CharField(
        widget=_CURRENT_PASSWORD_WIDGET,
        label='Company Password',
        help_text="Your company's shared registration password.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        # role is intentionally excluded — new users always start as 'employee'
        # and an admin promotes them if needed
        fields = ['first_name', 'last_name', 'email', 'phone']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True

    def clean(self):
        cleaned_data = super().clean()
        domain = cleaned_data.get('company_domain', '').lower().strip()
        company_pw = cleaned_data.get('company_password', '').strip()

        if not domain:
            self.add_error('company_domain', 'Please enter your company domain.')
        if not company_pw:
            self.add_error('company_password', 'Please enter the company password.')

        if domain and company_pw:
            try:
                company = Company.objects.get(domain=domain, is_active=True)
            except Company.DoesNotExist:
                raise ValidationError('No active company found with that domain.')

            if not company.check_company_password(company_pw):
                raise ValidationError('Invalid company password.')

            cleaned_data['company'] = company

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.company = self.cleaned_data.get('company')
        user.role = 'employee'  # always start as employee; admin can promote
        if commit:
            user.save()
        return user


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class CompanyLoginForm(AuthenticationForm):
    """Login requiring company domain + user email + password."""

    company_domain = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'placeholder': 'your-company-domain', 'autocomplete': 'organization'}),
    )

    # Move company_domain to the top of the rendered form
    field_order = ['company_domain', 'username', 'password']

    def clean(self):
        cleaned_data = super().clean()
        domain = cleaned_data.get('company_domain', '').lower().strip()
        email = cleaned_data.get('username', '').lower().strip()
        password = cleaned_data.get('password')

        if not (domain and email and password):
            return cleaned_data

        # Verify company exists and is active
        try:
            company = Company.objects.get(domain=domain, is_active=True)
        except Company.DoesNotExist:
            raise ValidationError('No active company found with that domain.')

        # Verify user belongs to this company
        if not User.objects.filter(email=email, company=company, is_active=True).exists():
            # Use a generic message to avoid user-enumeration
            raise ValidationError('Invalid credentials.')

        # Authenticate password
        user = authenticate(self.request, username=email, password=password)
        if user is None:
            raise ValidationError('Invalid credentials.')

        cleaned_data['user'] = user
        cleaned_data['company'] = company
        return cleaned_data


# ---------------------------------------------------------------------------
# Profile forms
# ---------------------------------------------------------------------------

class UserProfileForm(forms.ModelForm):
    """Let users edit their own profile. Email is read-only."""

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'department', 'position']
        widgets = {
            'email': forms.EmailInput(attrs={'readonly': True}),
        }

    def clean_email(self):
        # Always return the original email — ignore any tampering
        return self.instance.email


class UserManagementForm(forms.ModelForm):
    """Allow company admins to manage user roles and details."""

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'department', 'position', 'role', 'is_active']
        widgets = {
            'email': forms.EmailInput(attrs={'readonly': True}),
        }

    def clean_email(self):
        return self.instance.email


class CompanyProfileForm(forms.ModelForm):
    """Allow company admins to edit company details. Domain is read-only."""

    class Meta:
        model = Company
        fields = ['name', 'domain', 'contact_email', 'contact_phone', 'address', 'subscription_plan', 'is_active']
        widgets = {
            'domain': forms.TextInput(attrs={'readonly': True}),
            'address': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_domain(self):
        # Domain must never change after creation
        return self.instance.domain


# ---------------------------------------------------------------------------
# Company password change
# ---------------------------------------------------------------------------

class CompanyPasswordChangeForm(forms.Form):
    """Allow company admins to rotate the shared company password."""

    current_company_password = forms.CharField(
        widget=_CURRENT_PASSWORD_WIDGET,
        label='Current Company Password',
    )
    new_company_password = forms.CharField(
        widget=_PASSWORD_WIDGET,
        label='New Company Password',
        min_length=8,
    )
    confirm_new_company_password = forms.CharField(
        widget=_PASSWORD_WIDGET,
        label='Confirm New Company Password',
    )

    def __init__(self, company: Company, *args, **kwargs):
        self.company = company
        super().__init__(*args, **kwargs)

    def clean_current_company_password(self):
        current = self.cleaned_data['current_company_password']
        if not self.company.check_company_password(current):
            raise ValidationError('Current company password is incorrect.')
        return current

    def clean(self):
        cleaned_data = super().clean()
        new_pw = cleaned_data.get('new_company_password')
        confirm = cleaned_data.get('confirm_new_company_password')
        if new_pw and confirm and new_pw != confirm:
            self.add_error('confirm_new_company_password', 'New passwords do not match.')
        return cleaned_data

    def save(self) -> None:
        self.company.set_company_password(self.cleaned_data['new_company_password'])
        self.company.save(update_fields=['company_password', 'updated_at'])