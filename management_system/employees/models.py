"""
employees/models.py — Department and Employee models, scoped per company tenant.
"""

import logging

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


class Department(models.Model):
    """A department within a company."""

    company = models.ForeignKey(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='departments',
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('company', 'name')]
        ordering = ['name']
        indexes = [
            models.Index(fields=['company', 'is_active']),
        ]

    def __str__(self) -> str:
        return f'{self.name} ({self.company.name})'

    @property
    def active_employee_count(self) -> int:
        return self.employees.filter(status='active').count()


class Employee(models.Model):
    ROLE_CHOICES = [
        ('manager', 'Manager'),
        ('developer', 'Developer'),
        ('designer', 'Designer'),
        ('analyst', 'Analyst'),
        ('engineer', 'Engineer'),
        ('intern', 'Intern'),
        ('hr', 'Human Resource'),
        ('accountant', 'Accountant'),
        ('secretary', 'Secretary'),
        ('project_manager', 'Project Manager'),
        ('stock_manager', 'Stock Manager'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('on_leave', 'On Leave'),
        ('terminated', 'Terminated'),
    ]

    company = models.ForeignKey(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='employees',
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='employee_profile',
    )
    employee_id = models.CharField(max_length=20)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='other', db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', db_index=True)
    position = models.ForeignKey(
        'hr.Position',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees',
        help_text='HR job position/grade for this employee.',
    )
    date_of_birth = models.DateField(null=True, blank=True)
    date_joined = models.DateField()
    salary = models.DecimalField(
        max_digits=12,           # raised from 10 → 12 to accommodate higher salaries
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=0,
    )
    photo = models.ImageField(upload_to='employees/photos/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('company', 'employee_id')]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['company', 'role']),
            models.Index(fields=['company', 'department']),
        ]

    def __str__(self) -> str:
        return f'{self.employee_id} — {self.full_name}'

    # ------------------------------------------------------------------
    # Convenience proxies to the related User
    # ------------------------------------------------------------------

    @property
    def full_name(self) -> str:
        return self.user.get_full_name()

    @property
    def email(self) -> str:
        return self.user.email

    @property
    def phone(self) -> str:
        return self.user.phone

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        return self.status == 'active'

    def terminate(self) -> None:
        """Mark the employee as terminated and deactivate their user account."""
        self.status = 'terminated'
        self.save(update_fields=['status', 'updated_at'])
        # Prevent the user from logging in after termination
        self.user.__class__.objects.filter(pk=self.user.pk).update(is_active=False)

    def reactivate(self) -> None:
        """Reactivate a previously terminated or inactive employee."""
        self.status = 'active'
        self.save(update_fields=['status', 'updated_at'])
        self.user.__class__.objects.filter(pk=self.user.pk).update(is_active=True)


# ---------------------------------------------------------------------------
# Signal: auto-create Employee profile on new User creation
# ---------------------------------------------------------------------------

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_employee_profile(sender, instance, created, **kwargs):
    """
    When a new User is saved and belongs to a company, automatically create
    a matching Employee record.

    NOTE: This signal is intentionally minimal — full employee details
    (salary, department, role) should be completed via the admin or
    the employee edit form.
    """
    if not created or not instance.company_id:
        return

    # Avoid duplicate creation (e.g. if called twice in tests)
    if Employee.objects.filter(user=instance).exists():
        return

    try:
        company = instance.company
        prefix = company.domain.upper()[:3]

        # Determine next sequential ID safely
        last = (
            Employee.objects
            .filter(company=company)
            .order_by('-id')
            .values_list('employee_id', flat=True)
            .first()
        )
        if last:
            try:
                next_num = int(last.split('-')[-1]) + 1
            except (ValueError, IndexError):
                next_num = Employee.objects.filter(company=company).count() + 1
        else:
            next_num = 1

        employee_id = f'{prefix}-{next_num:04d}'

        Employee.objects.create(
            company=company,
            user=instance,
            employee_id=employee_id,
            date_joined=timezone.now().date(),
            salary=0,
        )
        logger.info('Auto-created Employee profile %s for user %s', employee_id, instance.email)

    except Exception:
        # Never let a signal crash the user-creation request
        logger.exception('Failed to auto-create Employee profile for user %s', instance.email)