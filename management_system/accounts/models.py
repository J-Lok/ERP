import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.contrib.auth.hashers import make_password, check_password
from django.core.validators import RegexValidator


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

    company_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=200)
    domain = models.CharField(max_length=200, unique=True, db_index=True)
    company_password = models.CharField(max_length=256)  # increased from 128 → 256 for future hash algo headroom
    contact_email = models.EmailField()
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        validators=[RegexValidator(r'^\+?[\d\s\-().]{7,20}$', 'Enter a valid phone number.')],
    )
    address = models.TextField(blank=True)
    subscription_plan = models.CharField(
        max_length=20,
        choices=PLAN_CHOICES,
        default='free',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Companies'
        ordering = ['name']
        indexes = [
            models.Index(fields=['domain']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.name

    def set_company_password(self, raw_password: str) -> None:
        """Hash and store the company shared password."""
        self.company_password = make_password(raw_password)

    def check_company_password(self, raw_password: str) -> bool:
        """Verify a raw password against the stored hash."""
        return check_password(raw_password, self.company_password)

    @property
    def masked_password(self) -> str:
        """Return a masked placeholder — never expose the hash."""
        return '•' * 8 if self.company_password else ''

    @property
    def active_user_count(self) -> int:
        """Convenience accessor used in templates/admin."""
        return self.users.filter(is_active=True).count()


class CustomUserManager(BaseUserManager):
    """Custom manager for User model with email as the unique identifier."""

    def create_user(self, email: str, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set.')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if not extra_fields.get('is_staff'):
            raise ValueError('Superuser must have is_staff=True.')
        if not extra_fields.get('is_superuser'):
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom user model that uses email as the unique identifier.
    Each user belongs to a company (tenant).
    """
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('hr_manager', 'HR Manager'),
        ('accountant', 'Accountant'),
        ('manager', 'Manager'),
        ('secretary', 'Secretary'),
        ('stock_manager', 'Stock Manager'),
        ('employee', 'Employee'),
    ]

    username = None  # replaced by email
    email = models.EmailField(unique=True, db_index=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='users',
        null=True,
        blank=True,
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        validators=[RegexValidator(r'^\+?[\d\s\-().]{7,20}$', 'Enter a valid phone number.')],
    )
    department = models.CharField(max_length=100, blank=True)
    position = models.CharField(max_length=100, blank=True)
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='employee',
        db_index=True,
        help_text='User role for access control.',
    )
    is_company_admin = models.BooleanField(
        default=False,
        help_text='Designates whether the user can manage company settings.',
    )
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('fr', 'Français'),
    ]
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='en')

    # Audit / activity helpers
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        ordering = ['email']
        indexes = [
            models.Index(fields=['company', 'role']),
            models.Index(fields=['company', 'is_active']),
        ]

    def __str__(self) -> str:
        company_name = self.company.name if self.company else 'No Company'
        return f'{self.get_full_name()} <{self.email}> ({company_name})'

    def get_full_name(self) -> str:
        return f'{self.first_name} {self.last_name}'.strip() or self.email

    def has_role(self, *roles: str) -> bool:
        """Convenience helper: user.has_role('admin', 'manager')"""
        return self.is_superuser or self.role in roles

    @property
    def is_online(self) -> bool:
        """True if the user was active in the last 5 minutes."""
        if not self.last_seen:
            return False
        from django.utils import timezone
        from datetime import timedelta
        return (timezone.now() - self.last_seen) < timedelta(minutes=5)