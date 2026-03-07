from django.test import TestCase
from accounts.models import Company
from employees.models import Employee
from .models import Position, LeaveRequest


class HRModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Org', domain='org')
        # create a user and employee via signal if needed
        # create user; employee profile created automatically by signal
        from accounts.models import User as AuthUser
        user = AuthUser.objects.create_user(
            email='emp@example.com',
            password='password',
            company=self.company,
            first_name='Emp',
            last_name='Loyee'
        )
        # retrieve employee profile
        self.employee = user.employee_profile
        self.position = Position.objects.create(company=self.company, title='Developer', salary_grade=5)

    def test_leave_request(self):
        lr = LeaveRequest.objects.create(
            company=self.company,
            employee=self.employee,
            leave_type='vacation',
            start_date='2026-03-01',
            end_date='2026-03-05',
        )
        self.assertEqual(str(lr), f"{self.employee} vacation 2026-03-01")
        # status transitions
        lr.approve()
        self.assertEqual(lr.status, 'approved')
        lr.deny()
        self.assertEqual(lr.status, 'denied')
