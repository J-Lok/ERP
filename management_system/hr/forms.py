from django import forms
from .models import Position, LeaveRequest


class PositionForm(forms.ModelForm):
    class Meta:
        model = Position
        fields = ['title', 'salary_grade']


class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['employee', 'leave_type', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        if company:
            # limit employees to this company
            from employees.models import Employee
            self.fields['employee'].queryset = Employee.objects.filter(company=company)
