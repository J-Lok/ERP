from django.test import TestCase
from django.contrib.auth import get_user_model
from accounts.models import Company
from .models import Account, Transaction

User = get_user_model()


class FinanceModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='TestCo', domain='testco')
        # create user with required fields using custom manager
        self.user = User.objects.create_user(
            email='user1@example.com',
            password='password',
            company=self.company,
            first_name='User',
            last_name='One'
        )
        self.account = Account.objects.create(company=self.company, name='Cash', balance=1000)

    def test_transaction_creation(self):
        txn = Transaction.objects.create(
            company=self.company,
            account=self.account,
            transaction_type='credit',
            amount=50,
            date='2026-01-01',
            entered_by=self.user,
        )
        self.assertEqual(str(txn), 'credit 50 on Cash')
        # balance should have been updated on save
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 1050)
        # updating amount adjusts balance further
        txn.amount = 100
        txn.save()
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 1100)

    def test_balance_adjust_on_delete(self):
        txn = Transaction.objects.create(
            company=self.company,
            account=self.account,
            transaction_type='debit',
            amount=100,
            date='2026-01-02',
            entered_by=self.user,
        )
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 900)
        txn.delete()
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 1000)
