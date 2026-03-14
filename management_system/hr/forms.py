from django import forms
from django.core.exceptions import ValidationError

from .models import LeaveRequest, Position
from employees.models import Employee


class PositionForm(forms.ModelForm):
    class Meta:
        model = Position
        fields = ['title', 'description', 'salary_grade']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'salary_grade': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }


class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['employee', 'leave_type', 'start_date', 'end_date', 'reason']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'leave_type': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        company = kwargs.pop('company', None)
        self_employee = kwargs.pop('self_employee', None)  # for employee self-service
        super().__init__(*args, **kwargs)
        if company:
            self.fields['employee'].queryset = Employee.objects.filter(
                company=company, status__in=['active', 'on_leave']
            ).select_related('user')
        if self_employee:
            # Lock the employee field for self-service submissions
            self.fields['employee'].initial = self_employee
            self.fields['employee'].widget = forms.HiddenInput()
        self.fields['reason'].required = False

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        if start and end and end < start:
            raise ValidationError({'end_date': 'End date must be on or after the start date.'})
        return cleaned


class LeaveStatusForm(forms.ModelForm):
    """Minimal form used only to update status via approve/deny buttons."""
    class Meta:
        model = LeaveRequest
        fields = ['status']