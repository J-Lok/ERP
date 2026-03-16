"""
hr/models.py

Models:
  - Position      : Job title + salary grade, now linkable to Employee
  - LeaveRequest  : Time-off workflow with approve/deny, duration calc,
                    date validation, and automatic employee status sync
"""

import logging
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class Position(models.Model):
    """A named job title with a salary grade, scoped per company."""

    company = models.ForeignKey(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='positions',
    )
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    salary_grade = models.IntegerField(validators=[MinValueValidator(0)])

    class Meta:
        unique_together = [('company', 'title')]
        ordering = ['title']

    def __str__(self) -> str:
        return f'{self.title} (Grade {self.salary_grade})'

    @property
    def employee_count(self) -> int:
        return self.employees.filter(status='active').count()


class LeaveRequest(models.Model):
    LEAVE_TYPES = [
        ('vacation',  'Vacation'),
        ('sick',      'Sick Leave'),
        ('unpaid',    'Unpaid Leave'),
        ('maternity', 'Maternity Leave'),
        ('paternity', 'Paternity Leave'),
        ('other',     'Other'),
    ]
    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('denied',   'Denied'),
    ]

    company = models.ForeignKey(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='leaves',
    )
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='leaves',
    )
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True, help_text='Optional reason for the leave request.')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_leaves',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='submitted_leaves',
    )
    requested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['employee', 'status']),
            models.Index(fields=['start_date', 'end_date']),
        ]

    def __str__(self) -> str:
        return (
            f'{self.employee.full_name} — {self.get_leave_type_display()} '
            f'({self.start_date} → {self.end_date})'
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def clean(self):
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValidationError({
                    'end_date': 'End date must be on or after the start date.'
                })

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def duration_days(self) -> int:
        """Number of calendar days covered by the request (inclusive)."""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0

    @property
    def is_active(self) -> bool:
        """True if the leave is approved and currently ongoing."""
        today = timezone.localdate()
        return (
            self.status == 'approved'
            and self.start_date <= today <= self.end_date
        )

    @property
    def is_upcoming(self) -> bool:
        today = timezone.localdate()
        return self.status == 'approved' and self.start_date > today

    # ------------------------------------------------------------------
    # Approve / Deny
    # ------------------------------------------------------------------

    def approve(self, reviewed_by=None) -> None:
        """
        Approve the leave request and optionally set the employee's
        status to 'on_leave' if the leave starts today or earlier.
        """
        self.status = 'approved'
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

        # Auto-update employee status if leave is current
        today = timezone.localdate()
        if self.start_date <= today <= self.end_date:
            self.employee.__class__.objects.filter(pk=self.employee_id).update(status='on_leave')
            logger.info(
                'Employee %s set to on_leave after leave approval.',
                self.employee_id,
            )

    def deny(self, reviewed_by=None) -> None:
        """
        Deny the leave request. If the employee was set to on_leave
        because of this request, revert them to active.
        """
        was_approved = self.status == 'approved'
        self.status = 'denied'
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

        if was_approved:
            # Only revert if no other approved leave is currently active
            today = timezone.localdate()
            other_active = LeaveRequest.objects.filter(
                employee=self.employee,
                status='approved',
                start_date__lte=today,
                end_date__gte=today,
            ).exclude(pk=self.pk).exists()
            if not other_active:
                self.employee.__class__.objects.filter(
                    pk=self.employee_id, status='on_leave'
                ).update(status='active')