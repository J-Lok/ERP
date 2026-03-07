from django import forms
from .models import Account, Transaction


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ['name', 'balance']


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['account', 'transaction_type', 'amount', 'description', 'date']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        if company:
            self.fields['account'].queryset = Account.objects.filter(company=company)