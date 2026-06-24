from django import forms
from django.core.exceptions import ValidationError
from .models import Client, Order
from accounts.models import Company
from inventory.models import Stock

class ClientRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")

    class Meta:
        model = Client
        fields = ['first_name', 'last_name', 'email', 'phone', 'address', 'city', 'country', 'postal_code']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        # Check passwords match
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', 'Passwords do not match.')

        # Check if email already exists platform-wide
        email = cleaned_data.get('email')
        if email and Client.objects.filter(email=email).exists():
            self.add_error('email', 'An account with this email already exists.')

        return cleaned_data

    def save(self, commit=True):
        client = super().save(commit=False)
        client.set_password(self.cleaned_data['password'])

        if commit:
            client.save()
            # Create cart and wishlist for client
            from .models import Cart, Wishlist
            Cart.objects.create(client=client)
            Wishlist.objects.create(client=client)

        return client


class ClientLoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')

        if email and password:
            try:
                client = Client.objects.get(email=email, is_active=True)
                if not client.check_password(password):
                    raise ValidationError('Invalid email or password.')
                cleaned_data['client'] = client
            except Client.DoesNotExist:
                raise ValidationError('No account found with these credentials.')

        return cleaned_data


class ClientProfileForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['first_name', 'last_name', 'phone', 'address', 'city', 'country', 'postal_code']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }


class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['shipping_address', 'shipping_city', 'shipping_country', 'shipping_phone', 'notes']
        widgets = {
            'shipping_address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'shipping_city': forms.TextInput(attrs={'class': 'form-control'}),
            'shipping_country': forms.TextInput(attrs={'class': 'form-control'}),
            'shipping_phone': forms.TextInput(attrs={'class': 'form-control', 'type': 'tel'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Any special instructions?'}),
        }


class AddToCartForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, initial=1)


class QuickOrderForm(forms.Form):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('mobile', 'Mobile Money'),
        ('other', 'Other'),
    ]

    client = forms.ModelChoiceField(
        queryset=Client.objects.filter(is_active=True).order_by('first_name', 'last_name'),
        required=False,
        empty_label='Walk-in customer',
        label='Existing Client',
    )
    first_name = forms.CharField(required=False, max_length=100)
    last_name = forms.CharField(required=False, max_length=100)
    email = forms.EmailField(required=False)
    phone = forms.CharField(required=False, max_length=20)
    payment_method = forms.ChoiceField(choices=PAYMENT_METHOD_CHOICES, required=False)
    payment_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        label='Order Notes',
    )

    def __init__(self, company=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        stock_queryset = Stock.objects.none()
        if company is not None:
            stock_queryset = Stock.objects.filter(
                company=company,
                is_marketplace_visible=True,
                quantity__gt=0,
            ).order_by('name')

        for i in range(1, 6):
            self.fields[f'stock_{i}'] = forms.ModelChoiceField(
                queryset=stock_queryset,
                required=False,
                label=f'Product {i}',
            )
            self.fields[f'quantity_{i}'] = forms.IntegerField(
                min_value=1,
                required=False,
                initial=1,
                label=f'Quantity {i}',
            )

    def clean(self):
        cleaned_data = super().clean()
        client = cleaned_data.get('client')
        first_name = cleaned_data.get('first_name')
        last_name = cleaned_data.get('last_name')
        email = cleaned_data.get('email')

        item_rows = []
        for i in range(1, 6):
            stock = cleaned_data.get(f'stock_{i}')
            quantity = cleaned_data.get(f'quantity_{i}')
            if stock and quantity:
                if stock.quantity < quantity:
                    self.add_error(
                        f'quantity_{i}',
                        f'Only {stock.quantity} units available for {stock.name}.'
                    )
                item_rows.append({'stock': stock, 'quantity': quantity})
            elif stock or quantity:
                self.add_error(
                    f'stock_{i}' if not stock else f'quantity_{i}',
                    'Both product and quantity are required for each row.'
                )

        if not item_rows:
            raise ValidationError('Please add at least one product to the order.')

        if not client:
            if not first_name or not last_name or not email:
                raise ValidationError(
                    'Select an existing client or provide first name, last name, and email for a walk-in customer.'
                )

        cleaned_data['items'] = item_rows
        return cleaned_data