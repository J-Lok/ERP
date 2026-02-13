from django import forms
from django.core.exceptions import ValidationError
from .models import Employee, Department
from accounts.models import User


class EmployeeForm(forms.ModelForm):
    """Form for creating or editing an employee"""

    create_user_account = forms.BooleanField(
        required=False,
        initial=True,
        label='Create user account',
        help_text='Create a new user account for this employee'
    )

    user_email = forms.EmailField(
        required=False,
        label='User Email',
        help_text='Email for the user account'
    )

    user_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput,
        label='User Password',
        help_text='Password for the user account'
    )

    existing_user_email = forms.EmailField(
        required=False,
        label='Existing User Email',
        help_text='Email of an existing user to link'
    )

    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)
    phone = forms.CharField(max_length=20, required=False)

    class Meta:
        model = Employee
        fields = [
            'employee_id', 'department', 'role', 'status',
            'date_of_birth', 'date_joined', 'salary', 'photo'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'date_joined': forms.DateInput(attrs={'type': 'date'}),
            'salary': forms.NumberInput(attrs={'step': '0.01'}),
        }
        help_texts = {
            'employee_id': 'Unique employee ID (e.g., EMP-001)',
            'salary': 'Annual salary in dollars',
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)

        # Filter departments to current company
        if self.company:
            self.fields['department'].queryset = Department.objects.filter(company=self.company)

        # Populate user fields if editing
        if self.instance and self.instance.pk and self.instance.user:
            self.fields['create_user_account'].initial = False
            self.fields['create_user_account'].disabled = True
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['phone'].initial = self.instance.user.phone
            self.fields['existing_user_email'].initial = self.instance.user.email

    def clean(self):
        cleaned_data = super().clean()
        create_user = cleaned_data.get('create_user_account')

        if create_user:
            # Validate required fields for new user
            email = cleaned_data.get('user_email')
            password = cleaned_data.get('user_password')
            first_name = cleaned_data.get('first_name')
            last_name = cleaned_data.get('last_name')
            if not all([email, password, first_name, last_name]):
                raise ValidationError('All user fields are required when creating a new user account.')
            if User.objects.filter(email=email).exists():
                self.add_error('user_email', 'This email is already registered.')
        else:
            # Validate linking existing user
            existing_email = cleaned_data.get('existing_user_email')
            
            # Skip validation if we're editing and the email hasn't changed
            if self.instance and self.instance.pk and self.instance.user:
                # This is an edit of an existing employee with a user
                # Skip the validation that would flag "already has employee profile"
                if existing_email == self.instance.user.email:
                    # Keep the existing user
                    cleaned_data['existing_user'] = self.instance.user
                    return cleaned_data
            
            if existing_email:
                try:
                    user = User.objects.get(email=existing_email, company=self.company)
                    # Check if this user already has an employee profile, but exclude the current employee
                    if hasattr(user, 'employee_profile'):
                        # If we're editing and this is the same employee, it's OK
                        if self.instance and self.instance.pk and user.employee_profile.pk == self.instance.pk:
                            # Same employee, it's fine
                            cleaned_data['existing_user'] = user
                        else:
                            # Different employee, error
                            self.add_error('existing_user_email', 'This user already has an employee profile.')
                    else:
                        cleaned_data['existing_user'] = user
                except User.DoesNotExist:
                    self.add_error('existing_user_email', 'User with this email does not exist in your company.')
            else:
                if not (self.instance and self.instance.pk and self.instance.user):
                    # Only require email if not editing an existing employee with a user
                    raise ValidationError('Please provide an existing user email to link.')

        # Validate unique employee_id per company
        employee_id = cleaned_data.get('employee_id')
        if employee_id and self.company:
            qs = Employee.objects.filter(company=self.company, employee_id=employee_id)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('employee_id', f'Employee ID "{employee_id}" already exists in your company.')

        return cleaned_data

    def save(self, commit=True):
        employee = super().save(commit=False)
        employee.company = self.company

        if self.cleaned_data.get('create_user_account'):
            # Create new user
            user = User.objects.create_user(
                email=self.cleaned_data['user_email'],
                password=self.cleaned_data['user_password'],
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name'],
                phone=self.cleaned_data.get('phone', ''),
                company=self.company
            )
            employee.user = user
        else:
            # Link existing user
            existing_user = self.cleaned_data.get('existing_user')
            if existing_user:
                employee.user = existing_user

        # Ensure salary is never None
        if employee.salary is None:
            employee.salary = 0.0

        if commit:
            employee.save()
        return employee


class DepartmentForm(forms.ModelForm):
    """Form for creating or editing a department"""

    class Meta:
        model = Department
        fields = ['name', 'description']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data['name']
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
