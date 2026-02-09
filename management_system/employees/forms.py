from django import forms
from django.core.exceptions import ValidationError
from .models import Employee, Department
from accounts.models import User

class EmployeeForm(forms.ModelForm):
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
        help_text='Email of existing user to link'
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
        
        if self.company:
            # Filter departments to only those in the company
            self.fields['department'].queryset = Department.objects.filter(company=self.company)
            
            # Set initial values for existing employee
            if self.instance and self.instance.pk:
                self.fields['create_user_account'].initial = False
                self.fields['create_user_account'].disabled = True
                
                if self.instance.user:
                    self.fields['first_name'].initial = self.instance.user.first_name
                    self.fields['last_name'].initial = self.instance.user.last_name
                    self.fields['phone'].initial = self.instance.user.phone
                    self.fields['existing_user_email'].initial = self.instance.user.email
    
    def clean(self):
        cleaned_data = super().clean()
        create_user_account = cleaned_data.get('create_user_account')
        
        if create_user_account:
            # Validate new user fields
            email = cleaned_data.get('user_email')
            password = cleaned_data.get('user_password')
            first_name = cleaned_data.get('first_name')
            last_name = cleaned_data.get('last_name')
            
            if not all([email, password, first_name, last_name]):
                raise ValidationError(
                    'All user fields are required when creating a new user account.'
                )
            
            # Check if email already exists
            if User.objects.filter(email=email).exists():
                self.add_error('user_email', 'This email is already registered.')
        else:
            # Validate existing user
            existing_email = cleaned_data.get('existing_user_email')
            if not existing_email:
                raise ValidationError(
                    'Please provide an existing user email.'
                )
            
            # Check if user exists in company
            try:
                user = User.objects.get(email=existing_email, company=self.company)
                cleaned_data['existing_user'] = user
            except User.DoesNotExist:
                self.add_error('existing_user_email', 
                    'User with this email does not exist in your company.'
                )
        
        # Validate employee ID uniqueness
        employee_id = cleaned_data.get('employee_id')
        if employee_id and self.company:
            queryset = Employee.objects.filter(company=self.company, employee_id=employee_id)
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            
            if queryset.exists():
                self.add_error('employee_id', 
                    f'Employee ID "{employee_id}" already exists in your company.'
                )
        
        return cleaned_data
    
    def save(self, commit=True):
        employee = super().save(commit=False)
        employee.company = self.company
        
        if commit:
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
                # Link to existing user
                existing_user = self.cleaned_data.get('existing_user')
                if existing_user:
                    employee.user = existing_user
            
            employee.save()
        
        return employee

class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
    
    def clean_name(self):
        name = self.cleaned_data['name']
        if self.company:
            queryset = Department.objects.filter(company=self.company, name=name)
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            
            if queryset.exists():
                raise ValidationError(f'Department "{name}" already exists in your company.')
        
        return name
    
    def save(self, commit=True):
        department = super().save(commit=False)
        if self.company:
            department.company = self.company
        
        if commit:
            department.save()
        
        return department