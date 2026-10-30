from datetime import date, timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from accounts.models import Company, User
from employees.models import Employee
from hr.models import (
    Position,
    LeaveRequest,
    SalaryComponent,
    PayrollPeriod,
    PayrollEntry,
    PayrollEntryComponent,
    Payslip,
    PerformanceGoal,
    PerformanceReview,
    Skill,
    EmployeeSkill,
)


class HRModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name='Org', domain='org', contact_email='org@example.com'
        )
        self.user = User.objects.create_user(
            email='emp@example.com',
            password='password',
            company=self.company,
            first_name='Emp',
            last_name='Loyee'
        )
        self.employee = self.user.employee_profile
        self.employee.salary = Decimal('2500.00')
        self.employee.save()
        self.position = Position.objects.create(
            company=self.company, title='Developer', salary_grade=5
        )

    def test_leave_request(self):
        lr = LeaveRequest.objects.create(
            company=self.company,
            employee=self.employee,
            leave_type='vacation',
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 5),
        )
        self.assertEqual(str(lr), "Emp Loyee — Vacation (2026-03-01 → 2026-03-05)")
        lr.approve()
        self.assertEqual(lr.status, 'approved')
        lr.deny()
        self.assertEqual(lr.status, 'denied')

    def test_leave_request_date_validation(self):
        invalid_lr = LeaveRequest(
            company=self.company,
            employee=self.employee,
            leave_type='sick',
            start_date=date(2026, 3, 10),
            end_date=date(2026, 3, 5),
        )
        with self.assertRaises(ValidationError):
            invalid_lr.clean()

    def test_payroll_period_and_calculation_workflow(self):
        period = PayrollPeriod.objects.create(
            company=self.company,
            period_type='monthly',
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
        )
        self.assertEqual(period.status, 'draft')

        # Create salary components
        base_comp = SalaryComponent.objects.create(
            company=self.company,
            name='Base Pay',
            component_type='earning',
        )
        tax_comp = SalaryComponent.objects.create(
            company=self.company,
            name='Income Tax',
            component_type='tax',
        )

        # Create entry
        entry = PayrollEntry.objects.create(
            payroll_period=period,
            employee=self.employee,
        )
        PayrollEntryComponent.objects.create(
            payroll_entry=entry,
            component=base_comp,
            amount=Decimal('3000.00'),
        )
        PayrollEntryComponent.objects.create(
            payroll_entry=entry,
            component=tax_comp,
            amount=Decimal('300.00'),
        )

        entry.calculate_totals()
        self.assertEqual(entry.gross_earnings, Decimal('3000.00'))
        self.assertEqual(entry.tax_amount, Decimal('300.00'))
        self.assertEqual(entry.net_pay, Decimal('2700.00'))

        # Lock period
        period.lock()
        self.assertEqual(period.status, 'locked')

        # Process period and auto-generate payslip
        period.process(processed_by=self.user)
        self.assertEqual(period.status, 'completed')
        self.assertEqual(period.total_earnings, Decimal('3000.00'))
        self.assertEqual(period.total_net_pay, Decimal('2700.00'))

        # Verify payslip was automatically created
        payslip = Payslip.objects.get(payroll_entry=entry)
        self.assertIsNotNone(payslip.payslip_number)

    def test_performance_management(self):
        goal = PerformanceGoal.objects.create(
            company=self.company,
            employee=self.employee,
            title='Deliver API V2',
            description='Complete REST endpoints with test coverage',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            progress=60,
            created_by=self.user,
        )
        self.assertEqual(goal.progress, 60)

        review = PerformanceReview.objects.create(
            company=self.company,
            employee=self.employee,
            reviewer=self.user,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 6, 30),
            review_date=date.today(),
            rating=5,
            strengths='Strong problem solver',
        )
        self.assertEqual(review.rating, 5)

    def test_skills_matrix(self):
        skill = Skill.objects.create(
            company=self.company,
            name='Python / Django',
            category='technical',
        )
        emp_skill = EmployeeSkill.objects.create(
            employee=self.employee,
            skill=skill,
            proficiency_level=4,
            assessed_by=self.user,
            assessment_date=date.today(),
        )
        self.assertEqual(emp_skill.proficiency_level, 4)
