from django import forms
from .models import Contact, Opportunity


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ['name', 'email', 'phone', 'organization']


class OpportunityForm(forms.ModelForm):
    class Meta:
        model = Opportunity
        fields = ['contact', 'title', 'stage', 'value']

    def __init__(self, *args, **kwargs):
        company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        if company:
            self.fields['contact'].queryset = Contact.objects.filter(company=company)
