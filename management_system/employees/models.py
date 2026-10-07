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


# Seeded into every new company so the role picker isn't empty on day one.
# Purely a starting point — companies can rename, deactivate or add their own
# roles at any time via JobRole.
DEFAULT_JOB_ROLE_NAMES = [
    'Manager', 'Developer', 'Designer', 'Analyst', 'Engineer', 'Intern',
    'Human Resource', 'Accountant', 'Secretary', 'Project Manager',
    'Stock Manager', 'Other',
]


class JobRole(models.Model):
    """A job role/title for employees (e.g. Developer, Manager).

    Company-scoped and freely extensible — unlike Django model choices,
    new roles can be created at any time from the employee form.
    """

    company = models.ForeignKey(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='job_roles',
    )
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('company', 'name')]
        ordering = ['name']

    def __str__(self) -> str:
        return self.name

    @property
    def slug(self) -> str:
        """Normalised key used to map this role to a User access level."""
        return self.name.strip().lower().replace(' ', '_')


class Employee(models.Model):
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
    role = models.ForeignKey(
        JobRole,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees',
    )
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
            models.Index(fields=['company', 'role'], name='employees_company_role_idx'),
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


def generate_employee_id(company) -> str:
    """Next sequential employee ID for a company, e.g. 'ACM-0004'.

    Shared by the auto-create signal below and EmployeeForm, so the ID shown
    (read-only) on the create form is the exact one that will be saved.
    """
    prefix = company.domain.upper()[:3]

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

    return f'{prefix}-{next_num:04d}'


def seed_default_job_roles(company) -> None:
    """Ensure the starter set of JobRoles exists for a company.

    Idempotent and additive: only creates whichever default role names are
    still missing, so it's safe to re-run on every deploy (via the
    seed_job_roles management command) without touching roles a company has
    since renamed, deactivated, or added on its own.
    """
    existing = set(
        JobRole.objects.filter(company=company, name__in=DEFAULT_JOB_ROLE_NAMES)
        .values_list('name', flat=True)
    )
    missing = [name for name in DEFAULT_JOB_ROLE_NAMES if name not in existing]
    if missing:
        JobRole.objects.bulk_create([JobRole(company=company, name=name) for name in missing])


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
        seed_default_job_roles(company)
        employee_id = generate_employee_id(company)

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