from django.contrib import admin
from .models import Account, Transaction

# Register your models here.


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'balance', 'created_at')
    search_fields = ('name',)
    list_filter = ('company',)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('account', 'transaction_type', 'amount', 'date', 'company')
    list_filter = ('transaction_type', 'date', 'company')
    search_fields = ('account__name', 'description')
    date_hierarchy = 'date'