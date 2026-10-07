import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils import timezone

RESERVED_COMPANY_DOMAINS = {
    'admin', 'core', 'employees', 'projects', 'inventory', 'marketplace', 'finance',
    'hr', 'crm', 'meetings', 'notifications', 'login', 'logout', 'register', 'invite',
    'password-change', 'password-reset', 'reset', 'language', 'static', 'media', 'api'
}


class Company(models.Model):
    PLAN_CHOICES = [
        ('free', 'Free'),
        ('basic', 'Basic'),
        ('premium', 'Premium'),
        ('enterprise', 'Enterprise'),
    ]

    CURRENCY_CHOICES = [
        ('XAF', 'FCFA — Central Africa (XAF)'),
        ('XOF', 'FCFA — West Africa (XOF)'),
        ('USD', 'US Dollar ($)'),
        ('EUR', 'Euro (€)'),
        ('GBP', 'British Pound (£)'),
        ('NGN', 'Nigerian Naira (₦)'),
        ('GHS', 'Ghanaian Cedi (₵)'),
        ('ZAR', 'South African Rand (R)'),
        ('CAD', 'Canadian Dollar (CA$)'),
    ]

    company_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=200)
    domain = models.CharField(max_length=200, unique=True, db_index=True)
    contact_email = models.EmailField()
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        validators=[RegexValidator(r'^\+?[\d\s\-().]{7,20}$', 'Enter a valid phone number.')],
    )
    whatsapp_number = models.CharField(
        max_length=30,
        blank=True,
        help_text='WhatsApp contact number for marketplace clients (e.g. +2376XXXXXXXX)',
    )
    orange_money_number = models.CharField(
        max_length=30,
        blank=True,
        help_text='Orange Money transaction number for client payments',
    )
    mtn_momo_number = models.CharField(
        max_length=30,
        blank=True,
        help_text='MTN Mobile Money transaction number for client payments',
    )
    address = models.TextField(blank=True)
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='XAF',
        help_text='Currency used for all prices displayed across the application.',
    )
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

    def clean(self):
        super().clean()
        domain = (self.domain or '').strip().lower()
        if domain in RESERVED_COMPANY_DOMAINS:
            raise ValidationError({'domain': f"Domain '{domain}' is reserved and cannot be used."})

    def save(self, *args, **kwargs):
        # Only enforce the reserved-domain rule here, not the whole model:
        # full_clean() would also require contact_email etc. on every save,
        # breaking any caller (scripts, admin, partial updates) that only sets
        # a subset of fields. Forms still run full validation via is_valid().
        self.clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    CURRENCY_SYMBOLS = {
        'XAF': 'FCFA',
        'XOF': 'FCFA',
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'NGN': '₦',
        'GHS': '₵',
        'ZAR': 'R',
        'CAD': 'CA$',
    }

    @property
    def currency_symbol(self) -> str:
        """Display symbol for this company's currency, e.g. 'XAF' -> 'FCFA'."""
        return self.CURRENCY_SYMBOLS.get(self.currency, self.currency)

    def to_display_currency(self, usd_amount):
        """Convert a USD amount (as stored in the database) to this
        company's selected display currency, using the shared ExchangeRate
        table. Every monetary field in the app is stored in USD — this is
        the one place that conversion happens, at display time."""
        if usd_amount is None:
            return None
        return usd_amount * get_exchange_rates().get(self.currency, Decimal('1'))

    def from_display_currency(self, display_amount):
        """Inverse of to_display_currency() — convert a value typed by a
        user in this company's display currency back to USD for storage."""
        if display_amount is None:
            return None
        rate = get_exchange_rates().get(self.currency, Decimal('1'))
        if not rate:
            return display_amount
        return display_amount / rate

    @property
    def active_user_count(self) -> int:
        return self.users.filter(is_active=True).count()

    @property
    def pending_invitations_count(self) -> int:
        return self.invitations.filter(accepted_at__isnull=True, expires_at__gt=timezone.now()).count()


EXCHANGE_RATES_CACHE_KEY = 'accounts:exchange_rates_usd'
EXCHANGE_RATES_CACHE_TTL = 300  # seconds — also cleared explicitly whenever rates are saved


def get_exchange_rates() -> dict:
    """{currency_code: Decimal rate}, one entry per currently supported
    currency. Read on virtually every page render (every converted amount),
    so it's cached briefly rather than hitting the DB each time."""
    rates = cache.get(EXCHANGE_RATES_CACHE_KEY)
    if rates is None:
        rates = {row.currency: row.rate for row in ExchangeRate.objects.all()}
        cache.set(EXCHANGE_RATES_CACHE_KEY, rates, EXCHANGE_RATES_CACHE_TTL)
    return rates


class ExchangeRate(models.Model):
    """
    Platform-wide USD exchange rate for one of Company.CURRENCY_CHOICES.

    Shared by every company — a company only picks *which* currency it
    displays in (Company.currency); the rate itself is a market fact, not a
    per-tenant setting. Either set manually or refreshed in bulk from a free
    FX API via the "Update rates" action.
    """
    currency = models.CharField(max_length=3, choices=Company.CURRENCY_CHOICES, unique=True)
    rate = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=1,
        help_text='Units of this currency equal to 1 USD.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['currency']

    def __str__(self):
        return f'{self.currency} = {self.rate} USD'

    @property
    def symbol(self) -> str:
        return Company.CURRENCY_SYMBOLS.get(self.currency, self.currency)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(EXCHANGE_RATES_CACHE_KEY)

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        cache.delete(EXCHANGE_RATES_CACHE_KEY)


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
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('hr_manager', 'HR Manager'),
        ('accountant', 'Accountant'),
        ('manager', 'Manager'),
        ('secretary', 'Secretary'),
        ('stock_manager', 'Stock Manager'),
        ('employee', 'Employee'),
    ]

    # Roles a company admin can hand out via invitation. 'admin' is excluded
    # on purpose — there is exactly one admin per company (the founder, set
    # at company_register time), and no UI promotes anyone else to it.
    INVITABLE_ROLE_CHOICES = [c for c in ROLE_CHOICES if c[0] != 'admin']

    username = None  # replaced by email
    email = models.EmailField(unique=True, db_index=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
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
        return self.is_superuser or self.role in roles

    @property
    def is_online(self) -> bool:
        if not self.last_seen:
            return False
        return (timezone.now() - self.last_seen) < timedelta(minutes=5)


class Invitation(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField()
    role = models.CharField(
        max_length=20,
        choices=User.INVITABLE_ROLE_CHOICES,
        default='employee',
        help_text='Access level the invitee will have once they accept.',
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_invitations',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('company', 'email')
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['company', 'email']),
        ]

    def __str__(self):
        status = 'accepted' if self.accepted_at else ('expired' if self.is_expired else 'pending')
        return f'Invite {self.email} → {self.company.name} [{status}]'

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @property
    def is_pending(self) -> bool:
        return self.accepted_at is None and not self.is_expired

    @classmethod
    def create_for(cls, company, email: str, invited_by, role: str = 'employee') -> 'Invitation':
        """Create (or reset) an invitation for a given email+company."""
        cls.objects.filter(company=company, email=email, accepted_at__isnull=True).delete()
        return cls.objects.create(
            company=company,
            email=email,
            role=role,
            invited_by=invited_by,
            expires_at=timezone.now() + timedelta(days=7),
        )


class CompanyEmailSettings(models.Model):
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='email_settings')
    email_host = models.CharField(max_length=255, default='smtp.gmail.com')
    email_port = models.IntegerField(default=587)
    email_use_tls = models.BooleanField(default=True)
    email_host_user = models.CharField(max_length=255)
    email_host_password = models.CharField(max_length=255)
    default_from_email = models.EmailField(default='no-reply@zentral.com')
    is_active = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Company Email Settings'
        verbose_name_plural = 'Company Email Settings'

    def __str__(self):
        return f"Email Settings for {self.company.name}"