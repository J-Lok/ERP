from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator

# Create your models here.


class Position(models.Model):
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='positions')
    title = models.CharField(max_length=100)
    salary_grade = models.IntegerField(validators=[MinValueValidator(0)])

    class Meta:
        unique_together = ['company', 'title']
        ordering = ['title']

    def __str__(self):
        return f"{self.title} ({self.company.name})"


class LeaveRequest(models.Model):
    LEAVE_TYPES = [
        ('vacation', 'Vacation'),
        ('sick', 'Sick'),
        ('unpaid', 'Unpaid'),
        ('maternity', 'Maternity'),
        ('paternity', 'Paternity'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
    ]

    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='leaves')
    employee = models.ForeignKey('employees.Employee', on_delete=models.CASCADE, related_name='leaves')
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f"{self.employee} {self.leave_type} {self.start_date}"

    def approve(self, approved_by=None):
        """Mark this leave request as approved."""
        self.status = 'approved'
        self.save()
        # potential: add audit log here

    def deny(self, denied_by=None):
        """Mark this leave request as denied."""
        self.status = 'denied'
        self.save()