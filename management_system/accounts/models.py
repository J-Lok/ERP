import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.contrib.auth.hashers import make_password, check_password
from django.core.exceptions import ValidationError


class Company(models.Model):
    """
    Represents a tenant (company) in the system.
    Each company has its own shared password for team member registration.
    """
    PLAN_CHOICES = [
        ('free', 'Free'),
        ('basic', 'Basic'),
        ('premium', 'Premium'),
        ('enterprise', 'Enterprise'),
    ]

    # Public identifier (optional, alongside auto-increment id)
    company_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=200)
    domain = models.CharField(max_length=200, unique=True, db_index=True)
    # Company password is stored as a Django hash (via make_password)
    company_password = models.CharField(max_length=128)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    subscription_plan = models.CharField(
        max_length=20,
        choices=PLAN_CHOICES,
        default='free'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Companies"
        ordering = ['name']
        indexes = [
            models.Index(fields=['domain']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.name

    def set_company_password(self, raw_password):
        """Hash and set the company password."""
        self.company_password = make_password(raw_password)

    def check_company_password(self, raw_password):
        """Verify a raw password against the stored hash."""
        return check_password(raw_password, self.company_password)

    @property
    def masked_password(self):
        """Return a masked version of the password for display (never show the hash)."""
        return "•" * 8 if self.company_password else ""


class CustomUserManager(BaseUserManager):
    """Custom manager for User model with email as the unique identifier."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom user model that uses email as the username.
    Each user belongs to a company.
    """
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('hr_manager', 'HR Manager'),
        ('accountant', 'Accountant'),
        ('manager', 'Manager'),
        ('secretary', 'Secretary'),
        ('employee', 'Employee'),
    ]

    username = None  # Remove username field
    email = models.EmailField(unique=True, db_index=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='users',
        null=True,       # Allow users without a company? Adjust as needed.
        blank=True
    )
    phone = models.CharField(max_length=20, blank=True)
    department = models.CharField(max_length=100, blank=True)
    position = models.CharField(max_length=100, blank=True)
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='employee',
        help_text="User role for access control"
    )
    is_company_admin = models.BooleanField(
        default=False,
        help_text="Designates whether the user can manage the company."
    )

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        ordering = ['email']
        # If email should be unique per company, add a UniqueConstraint.
        # Currently email is globally unique. Change if needed:
        # constraints = [
        #     models.UniqueConstraint(fields=['company', 'email'], name='unique_email_per_company')
        # ]

    def __str__(self):
        company_name = self.company.name if self.company else 'No Company'
        return f"{self.email} ({company_name})"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()