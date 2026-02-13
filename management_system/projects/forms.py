from django import forms
from django.core.exceptions import ValidationError
from .models import Project, SousTache, CommentaireTache
from employees.models import Employee

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = [
            'name', 'description', 'status', 'priority', 'manager',
            'team_members', 'budget', 'start_date', 'end_date', 'completion_percentage'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'budget': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'completion_percentage': forms.NumberInput(attrs={
                'min': 0, 
                'max': 100, 
                'class': 'form-control'
            }),
            'team_members': forms.SelectMultiple(attrs={'class': 'form-control select2'}),
            'manager': forms.Select(attrs={'class': 'form-control select2'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        
        if self.company:
            # Filter employees to only those in the company
            employees = Employee.objects.filter(company=self.company)
            self.fields['manager'].queryset = employees
            self.fields['team_members'].queryset = employees
            
            # Set initial completion percentage based on existing tasks if project exists
            if self.instance and self.instance.pk and self.instance.sous_taches.exists():
                # Calculate completion from tasks
                tasks = self.instance.sous_taches.all()
                total_tasks = tasks.count()
                completed_tasks = tasks.filter(status='termine').count()
                if total_tasks > 0:
                    calculated_progress = int((completed_tasks / total_tasks) * 100)
                    self.fields['completion_percentage'].initial = calculated_progress
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            self.add_error('end_date', 'End date must be after start date.')
        
        # Validate budget
        budget = cleaned_data.get('budget')
        if budget and budget < 0:
            self.add_error('budget', 'Budget cannot be negative.')
        
        return cleaned_data

class SousTacheForm(forms.ModelForm):
    class Meta:
        model = SousTache
        fields = [
            'titre', 'description', 'assigne_a', 'status', 'priorite',
            'date_debut', 'date_echeance', 'duree_estimee', 'ordre', 'depend_de'
        ]
        widgets = {
            'date_debut': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_echeance': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'duree_estimee': forms.NumberInput(attrs={
                'min': 0, 
                'class': 'form-control',
                'placeholder': 'Estimated hours'
            }),
            'ordre': forms.NumberInput(attrs={
                'min': 0, 
                'class': 'form-control',
                'placeholder': 'Display order'
            }),
            'assigne_a': forms.Select(attrs={'class': 'form-control select2'}),
            'depend_de': forms.Select(attrs={'class': 'form-control select2'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        projet_id = kwargs.pop('projet_id', None)
        super().__init__(*args, **kwargs)
        
        if self.company and projet_id:
            # Filter employees to only those in the company
            employees = Employee.objects.filter(company=self.company)
            self.fields['assigne_a'].queryset = employees
            
            # Filter dependencies to only those in the same project
            self.fields['depend_de'].queryset = SousTache.objects.filter(
                company=self.company,
                projet_id=projet_id
            ).exclude(id=self.instance.id if self.instance.id else None)
            
            # Set default order
            if not self.instance.pk:
                last_task = SousTache.objects.filter(
                    company=self.company,
                    projet_id=projet_id
                ).order_by('-ordre').first()
                self.fields['ordre'].initial = (last_task.ordre + 1) if last_task else 0
    
    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        date_echeance = cleaned_data.get('date_echeance')
        
        if date_debut and date_echeance and date_debut > date_echeance:
            self.add_error('date_echeance', 'Due date must be after start date.')
        
        # Validate estimated duration
        duree_estimee = cleaned_data.get('duree_estimee')
        if duree_estimee and duree_estimee < 0:
            self.add_error('duree_estimee', 'Estimated duration cannot be negative.')
        
        return cleaned_data

class CommentaireForm(forms.ModelForm):
    class Meta:
        model = CommentaireTache
        fields = ['contenu']
        widgets = {
            'contenu': forms.Textarea(attrs={
                'rows': 3, 
                'class': 'form-control',
                'placeholder': 'Add a comment...'
            })
        }