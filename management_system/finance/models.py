from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import transaction as db_transaction

# Create your models here.


class Account(models.Model):
    """Financial account scoped to company."""
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='accounts')
    name = models.CharField(max_length=100)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                  validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['company', 'name']
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.company.name})"


class Transaction(models.Model):
    TYPE_CHOICES = [
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    ]

    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='transactions')
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)])
    description = models.TextField(blank=True)
    date = models.DateField()
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.transaction_type} {self.amount} on {self.account.name}"


    def save(self, *args, **kwargs):
        # adjust account balance when transactions are created or updated
        with db_transaction.atomic():
            is_new = self.pk is None
            previous_amount = None
            previous_type = None
            if not is_new:
                old = Transaction.objects.select_for_update().get(pk=self.pk)
                previous_amount = old.amount
                previous_type = old.transaction_type
            super().save(*args, **kwargs)
            # compute balance delta
            if is_new:
                delta = self.amount if self.transaction_type == 'credit' else -self.amount
            else:
                prev_delta = previous_amount if previous_type == 'credit' else -previous_amount
                curr_delta = self.amount if self.transaction_type == 'credit' else -self.amount
                delta = curr_delta - prev_delta
            # use select_for_update on account as well
            acct = self.account
            acct.balance = models.F('balance') + delta
            acct.save(update_fields=['balance'])

    def delete(self, *args, **kwargs):
        with db_transaction.atomic():
            delta = -self.amount if self.transaction_type == 'credit' else self.amount
            acct = self.account
            acct.balance = models.F('balance') + delta
            acct.save(update_fields=['balance'])
            super().delete(*args, **kwargs)