"""
employees/forms.py
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import User
from hr.models import Position
from .models import Department, Employee


class EmployeeForm(forms.ModelForm):
    """
    Create or edit an employee.

    Two modes are supported:
      1. Create new user account  (create_user_account=True)
      2. Link to an existing user account  (create_user_account=False)

    Pass ``company=<Company>`` as a keyword argument so the department
    queryset is scoped to the correct tenant.
    """

    # ---- User-creation fields ----
    create_user_account = forms.BooleanField(
        required=False,
        initial=True,
        label='Create new user account',
        help_text='Uncheck to link an existing system user instead.',
    )
    user_email = forms.EmailField(
        required=False,
        label='Email',
        widget=forms.EmailInput(attrs={'autocomplete': 'email'}),
    )
    user_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        label='Password',
        min_length=8,
    )
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)
    phone = forms.CharField(max_length=20, required=False)

    # ---- Link-existing-user field ----
    existing_user_email = forms.EmailField(
        required=False,
        label='Existing User Email',
        help_text='Email of an existing user in your company.',
    )

    class Meta:
        model = Employee
        fields = [
            'employee_id', 'department', 'role', 'position', 'status',
            'date_of_birth', 'date_joined', 'salary', 'photo',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'date_joined': forms.DateInput(attrs={'type': 'date'}),
            'salary': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }
        help_texts = {
            'employee_id': 'Unique employee ID within your company (e.g. EMP-001).',
            'salary': 'Annual gross salary.',
            'position': 'HR job position / grade (optional — created in the HR module).',
        }

    def __init__(self, *args, company=None, **kwargs):
        self.company = company
        super().__init__(*args, **kwargs)

        if company:
            self.fields['department'].queryset = (
                Department.objects
                .filter(company=company, is_active=True)
                .order_by('name')
            )
            self.fields['position'].queryset = (
                Position.objects
                .filter(company=company)
                .order_by('title')
            )
            self.fields['position'].empty_label = '— No position assigned —'

        # Editing mode: pre-populate user fields, disable account creation toggle
        if self.instance and self.instance.pk and hasattr(self.instance, 'user') and self.instance.user_id:
            user = self.instance.user
            self.fields['create_user_account'].initial = False
            self.fields['create_user_account'].disabled = True
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['phone'].initial = user.phone
            self.fields['existing_user_email'].initial = user.email

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def clean_user_email(self):
        email = self.cleaned_data.get('user_email', '').strip().lower()
        return email

    def clean_date_joined(self):
        date_joined = self.cleaned_data.get('date_joined')
        if date_joined and date_joined > timezone.localdate():
            raise ValidationError('Date joined cannot be in the future.')
        return date_joined

    def clean(self):
        cleaned_data = super().clean()
        create_user = cleaned_data.get('create_user_account')

        if create_user:
            email = cleaned_data.get('user_email')
            password = cleaned_data.get('user_password')
            first_name = cleaned_data.get('first_name', '').strip()
            last_name = cleaned_data.get('last_name', '').strip()

            if not all([email, password, first_name, last_name]):
                raise ValidationError(
                    'First name, last name, email and password are all required '
                    'when creating a new user account.'
                )
            if User.objects.filter(email=email).exists():
                self.add_error('user_email', 'This email is already registered.')

        else:
            existing_email = cleaned_data.get('existing_user_email', '').strip().lower()
            is_edit = bool(self.instance and self.instance.pk and self.instance.user_id)

            if is_edit and self.instance.user.email == existing_email:
                # Unchanged — keep the existing user
                cleaned_data['existing_user'] = self.instance.user
            elif existing_email:
                try:
                    user = User.objects.get(email=existing_email, company=self.company)
                    if hasattr(user, 'employee_profile'):
                        # Allow if it's the same employee record being edited
                        if is_edit and user.employee_profile.pk == self.instance.pk:
                            cleaned_data['existing_user'] = user
                        else:
                            self.add_error(
                                'existing_user_email',
                                'This user already has an employee profile.',
                            )
                    else:
                        cleaned_data['existing_user'] = user
                except User.DoesNotExist:
                    self.add_error(
                        'existing_user_email',
                        'No user with this email found in your company.',
                    )
            elif not is_edit:
                raise ValidationError('Please provide an existing user email to link.')

        # Validate unique employee_id within the company
        employee_id = cleaned_data.get('employee_id', '').strip()
        if employee_id and self.company:
            qs = Employee.objects.filter(company=self.company, employee_id=employee_id)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('employee_id', f'Employee ID "{employee_id}" is already in use.')

        return cleaned_data

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    # Maps Employee.role (job title) → User.role (access level).
    # Employee roles with no special privileges map to 'employee'.
    EMPLOYEE_ROLE_TO_USER_ROLE = {
        'manager':         'manager',
        'project_manager': 'manager',
        'hr':              'hr_manager',
        'accountant':      'accountant',
        'secretary':       'secretary',
        'stock_manager':   'stock_manager',
        # developer, designer, analyst, engineer, intern, other → standard employee access
    }

    def _sync_user_role(self, user, employee_role: str) -> None:
        """Update User.role to match the Employee.role, then save."""
        new_user_role = self.EMPLOYEE_ROLE_TO_USER_ROLE.get(employee_role, 'employee')
        if user.role != new_user_role:
            user.role = new_user_role
            user.save(update_fields=['role'])

    def save(self, commit=True):
        employee = super().save(commit=False)
        employee.company = self.company

        if self.cleaned_data.get('create_user_account'):
            user = User.objects.create_user(
                email=self.cleaned_data['user_email'],
                password=self.cleaned_data['user_password'],
                first_name=self.cleaned_data['first_name'].strip(),
                last_name=self.cleaned_data['last_name'].strip(),
                phone=self.cleaned_data.get('phone', '').strip(),
                company=self.company,
            )
            employee.user = user
            self._sync_user_role(user, employee.role)
        else:
            existing_user = self.cleaned_data.get('existing_user')
            if existing_user:
                # Sync name/phone edits back to the linked user
                existing_user.first_name = self.cleaned_data.get('first_name', existing_user.first_name).strip()
                existing_user.last_name = self.cleaned_data.get('last_name', existing_user.last_name).strip()
                phone = self.cleaned_data.get('phone', '').strip()
                if phone:
                    existing_user.phone = phone
                existing_user.save(update_fields=['first_name', 'last_name', 'phone'])
                employee.user = existing_user
                self._sync_user_role(existing_user, employee.role)

        if not employee.salary:
            employee.salary = 0

        if commit:
            employee.save()
        return employee


class DepartmentForm(forms.ModelForm):
    """Create or edit a department. Pass ``company=<Company>`` as a kwarg."""

    class Meta:
        model = Department
        fields = ['name', 'description', 'is_active']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, company=None, **kwargs):
        self.company = company
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data['name'].strip().title()
        if self.company:
            qs = Department.objects.filter(company=self.company, name=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(f'Department "{name}" already exists in your company.')
        return name

    def save(self, commit=True):
        department = super().save(commit=False)
        if self.company:
            department.company = self.company
        if commit:
            department.save()
        return department