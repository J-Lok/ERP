"""
employees/forms.py
"""

from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import construct_instance
from django.utils import timezone
from django.utils.crypto import get_random_string

from accounts.models import User
from accounts.utils import CurrencyFieldsMixin
from hr.models import Position
from .models import Department, Employee, JobRole, generate_employee_id


class EmployeeForm(CurrencyFieldsMixin, forms.ModelForm):
    """
    Create or edit an employee.

    Two modes are supported:
      1. Create new user account  (create_user_account=True)
      2. Link to an existing user account  (create_user_account=False)

    Pass ``company=<Company>`` as a keyword argument so the department
    queryset is scoped to the correct tenant.

    When creating a new user account, a random password is generated
    server-side (never typed by the admin) and emailed to the new employee —
    see ``self.generated_password`` after a successful ``save()``.
    """

    currency_fields = ('salary',)

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
            'date_of_birth', 'salary', 'photo',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'salary': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'employee_id': forms.TextInput(attrs={'readonly': True}),
        }
        help_texts = {
            'employee_id': 'Auto-generated from your company domain — cannot be edited.',
            'salary': 'Annual gross salary.',
            'position': 'HR job position / grade (optional — created in the HR module).',
        }

    # Generated plaintext password for a newly-created user account. Only
    # ever held in memory for the lifetime of this form instance, never
    # persisted — the view uses it to send the welcome email, then it's gone.
    generated_password = None

    def __init__(self, *args, company=None, requester=None, **kwargs):
        self.company = company
        self._requester = requester
        super().__init__(*args, **kwargs)

        is_create = not (self.instance and self.instance.pk)

        # Read-only and always server-generated — never require a client-submitted value.
        self.fields['employee_id'].required = False

        if company:
            self.fields['department'].queryset = (
                Department.objects
                .filter(company=company, is_active=True)
                .order_by('name')
            )
            self.fields['role'].queryset = (
                JobRole.objects
                .filter(company=company, is_active=True)
                .order_by('name')
            )
            self.fields['role'].empty_label = '— No role assigned —'
            self.fields['position'].queryset = (
                Position.objects
                .filter(company=company)
                .order_by('title')
            )
            self.fields['position'].empty_label = '— No position assigned —'

            if is_create:
                self.fields['employee_id'].initial = generate_employee_id(company)

        # Editing mode: pre-populate user fields, disable account creation toggle
        if self.instance and self.instance.pk and hasattr(self.instance, 'user') and self.instance.user_id:
            user = self.instance.user
            self.fields['create_user_account'].initial = False
            self.fields['create_user_account'].disabled = True
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['phone'].initial = user.phone
            self.fields['existing_user_email'].initial = user.email

        self._convert_currency_fields_to_display()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def clean_user_email(self):
        email = self.cleaned_data.get('user_email', '').strip().lower()
        return email

    def clean(self):
        cleaned_data = super().clean()
        create_user = cleaned_data.get('create_user_account')
        is_create = not (self.instance and self.instance.pk)

        if create_user:
            email = cleaned_data.get('user_email')
            first_name = cleaned_data.get('first_name', '').strip()
            last_name = cleaned_data.get('last_name', '').strip()

            if not all([email, first_name, last_name]):
                raise ValidationError(
                    'First name, last name and email are all required '
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

        # employee_id is shown read-only and generated server-side — never
        # trust a client-submitted value for it. Regenerate on create so a
        # tampered field can't collide with another employee; on edit, it
        # can never change, so always fall back to the existing value.
        if is_create and self.company:
            cleaned_data['employee_id'] = generate_employee_id(self.company)
        elif not is_create:
            cleaned_data['employee_id'] = self.instance.employee_id

        # Validate unique employee_id within the company
        employee_id = cleaned_data.get('employee_id', '').strip()
        if employee_id and self.company:
            qs = Employee.objects.filter(company=self.company, employee_id=employee_id)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('employee_id', f'Employee ID "{employee_id}" is already in use.')

        return self._convert_currency_fields_to_usd(cleaned_data)

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

    def _sync_user_role(self, user, employee_role) -> None:
        """Update User.role to match the Employee.role, then save.

        ``employee_role`` is a JobRole instance (or None) — matched to a User
        access level via its slug (e.g. "Project Manager" -> "project_manager").
        Any role with no matching slug (including every custom role a company
        creates) falls back to standard 'employee' access.

        Safety rules:
        - Never demote a company_admin (is_company_admin=True).
        - Never demote users with admin/manager roles to a lower tier
          unless the form's requesting user is a company admin.
        - Never let a user elevate their own role.
        """
        # Never touch company admin flag holders.
        if user.is_company_admin:
            return

        role_slug = employee_role.slug if employee_role else None
        new_user_role = self.EMPLOYEE_ROLE_TO_USER_ROLE.get(role_slug, 'employee')

        # Requester context (may be None if called outside a request, e.g. import).
        requester = getattr(self, '_requester', None)

        # Prevent self-escalation.
        if requester and requester.pk == user.pk:
            return

        # Only company admins can grant privileged roles.
        PRIVILEGED_ROLES = {'admin', 'manager', 'hr_manager', 'accountant', 'stock_manager', 'secretary'}
        if new_user_role in PRIVILEGED_ROLES:
            if requester and not requester.is_company_admin:
                return  # silently skip — unprivileged user cannot grant privilege

        if user.role != new_user_role:
            user.role = new_user_role
            user.save(update_fields=['role'])

    def save(self, commit=True):
        if self.cleaned_data.get('create_user_account'):
            self.generated_password = get_random_string(12)
            user = User.objects.create_user(
                email=self.cleaned_data['user_email'],
                password=self.generated_password,
                first_name=self.cleaned_data['first_name'].strip(),
                last_name=self.cleaned_data['last_name'].strip(),
                phone=self.cleaned_data.get('phone', '').strip(),
                company=self.company,
            )
            self._sync_user_role(user, self.cleaned_data.get('role'))
            auto_employee = getattr(user, 'employee_profile', None)
            if auto_employee:
                # The post_save signal already created a bare Employee row
                # (employee_id/date_joined/salary only). Swapping self.instance
                # to it doesn't retroactively apply the form's cleaned_data —
                # _post_clean() already ran construct_instance() against the
                # original blank instance before this point — so re-run it
                # against the real instance now, or department/role/position/
                # status/salary/photo from this form would silently be lost.
                self.instance = auto_employee
                construct_instance(self, self.instance, self._meta.fields, self._meta.exclude)
            employee = super().save(commit=False)
            employee.company = self.company
            employee.user = user
        else:
            employee = super().save(commit=False)
            employee.company = self.company
            existing_user = self.cleaned_data.get('existing_user')
            if existing_user:
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

        if not employee.pk:
            employee.date_joined = timezone.now().date()

        if commit:
            employee.save()
        return employee


class DepartmentForm(forms.ModelForm):
    """Create or edit a department. Pass ``company=<Company>`` as a kwarg."""

    class Meta:
        model = Department
        fields = ['name', 'description', 'is_active']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, company=None, requester=None, **kwargs):
        self.company = company
        self._requester = requester
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


class JobRoleForm(forms.ModelForm):
    """Create or edit a job role. Pass ``company=<Company>`` as a kwarg."""

    class Meta:
        model = JobRole
        fields = ['name', 'is_active']

    def __init__(self, *args, company=None, requester=None, **kwargs):
        self.company = company
        self._requester = requester
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data['name'].strip().title()
        if self.company:
            qs = JobRole.objects.filter(company=self.company, name=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(f'Role "{name}" already exists in your company.')
        return name

    def save(self, commit=True):
        role = super().save(commit=False)
        if self.company:
            role.company = self.company
        if commit:
            role.save()
        return role