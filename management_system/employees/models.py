from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

class Department(models.Model):
    """Department model - scoped to company"""
    company = models.ForeignKey(
        'accounts.Company', on_delete=models.CASCADE, related_name='departments'
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['company', 'name']
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.company.name})"


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
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('on_leave', 'On Leave'),
        ('terminated', 'Terminated'),
    ]
    
    company = models.ForeignKey(
        'accounts.Company', on_delete=models.CASCADE, related_name='employees'
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='employee_profile'
    )
    employee_id = models.CharField(max_length=20)
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='employees'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='other')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    date_of_birth = models.DateField(null=True, blank=True)
    date_joined = models.DateField()
    salary = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], default=0
    )
    photo = models.ImageField(upload_to='employees/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['company', 'employee_id']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.employee_id} - {self.user.get_full_name()}"
    
    @property
    def full_name(self):
        return self.user.get_full_name()
    
    @property
    def email(self):
        return self.user.email
    
    @property
    def phone(self):
        return self.user.phone


# Signal to auto-create employee profile when a new user is created
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_employee_profile(sender, instance, created, **kwargs):
    if created and instance.company:
        # Generate a sequential employee ID per company
        company_prefix = instance.company.domain.upper()[:3]
        last_employee = Employee.objects.filter(company=instance.company).order_by('-id').first()
        next_id = 1 if not last_employee else int(last_employee.employee_id.split('-')[-1]) + 1
        employee_id = f"{company_prefix}-{next_id:04d}"

        # Create Employee profile with default salary
        Employee.objects.create(
            company=instance.company,
            user=instance,
            employee_id=employee_id,
            date_joined=getattr(instance, 'date_joined', timezone.now().date()),
            salary=0,  # Default salary for new employees
        )
