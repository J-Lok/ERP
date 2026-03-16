import logging

from django.contrib import messages
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import PasswordChangeView
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods

from .decorators import company_admin_required
from .forms import (
    CompanyCreationForm,
    UserRegistrationForm,
    CompanyLoginForm,
    UserProfileForm,
    CompanyProfileForm,
)
from .models import Company, User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

@require_http_methods(['GET', 'POST'])
def company_login(request):
    """Login with company domain + email + password."""
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = CompanyLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            login(request, user)

            if user.company:
                request.session['company_id'] = user.company.id

            # Capture login IP for audit
            _record_login_ip(request, user)

            messages.success(request, f'Welcome back, {user.first_name or user.email}!')
            next_url = request.GET.get('next') or 'core:dashboard'
            return redirect(next_url)
    else:
        form = CompanyLoginForm(request)

    return render(request, 'accounts/company_login.html', {
        'form': form,
        'title': 'Company Login',
    })


@require_http_methods(['GET', 'POST'])
def company_register(request):
    """Register a new company and its admin user."""
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = CompanyCreationForm(request.POST)
        if form.is_valid():
            company = form.save()

            email = form.cleaned_data['admin_email']
            password = form.cleaned_data['admin_password']

            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=form.cleaned_data['admin_first_name'],
                last_name=form.cleaned_data['admin_last_name'],
                company=company,
                is_company_admin=True,
                role='admin',
            )

            authenticated_user = authenticate(request, username=email, password=password)
            if authenticated_user is not None:
                login(request, authenticated_user)
                request.session['company_id'] = company.id
                messages.success(
                    request,
                    f'Welcome to {company.name}! Your company has been registered successfully.',
                )
                logger.info('New company registered: %s (admin: %s)', company.name, email)
                return redirect('core:dashboard')

            # Fallback — should not normally happen
            logger.warning('Auto-login failed after company registration for %s', email)
            messages.success(request, f'Company "{company.name}" registered! Please log in.')
            return redirect('accounts:company_login')
    else:
        form = CompanyCreationForm()

    return render(request, 'accounts/company_register.html', {
        'form': form,
        'title': 'Register Company',
    })


@require_http_methods(['GET', 'POST'])
def user_register(request):
    """Register a new user under an existing company."""
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            if user.company:
                request.session['company_id'] = user.company.id
            messages.success(request, f'Welcome to {user.company.name}, {user.first_name}!')
            return redirect('core:dashboard')
    else:
        form = UserRegistrationForm()

    return render(request, 'accounts/user_register.html', {
        'form': form,
        'title': 'Join Company',
    })


@require_http_methods(['GET', 'POST'])
@login_required
def custom_logout(request):
    """Log out and clear company session data."""
    request.session.pop('company_id', None)
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('accounts:company_login')


# ---------------------------------------------------------------------------
# Profile views
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(['GET', 'POST'])
def company_profile(request):
    """View/edit company profile — company admins only."""
    if not request.user.is_company_admin:
        raise PermissionDenied('Only company administrators can access this page.')

    company = request.user.company
    if company is None:
        messages.error(request, 'You are not associated with any company.')
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = CompanyProfileForm(request.POST, instance=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Company profile updated successfully!')
            return redirect('accounts:company_profile')
    else:
        form = CompanyProfileForm(instance=company)

    return render(request, 'accounts/company_profile.html', {
        'form': form,
        'company': company,
        'title': 'Company Profile',
    })


@login_required
def user_profile(request):
    """Display the current user's profile."""
    return render(request, 'accounts/user_profile.html', {
        'profile_user': request.user,   # avoid shadowing the built-in {{ user }}
        'title': 'My Profile',
    })


@login_required
@require_http_methods(['GET', 'POST'])
def edit_profile(request):
    """Edit the current user's profile."""
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('accounts:user_profile')
    else:
        form = UserProfileForm(instance=request.user)

    return render(request, 'accounts/edit_profile.html', {
        'form': form,
        'title': 'Edit Profile',
    })


# ---------------------------------------------------------------------------
# Password management
# ---------------------------------------------------------------------------

class CustomPasswordChangeView(PasswordChangeView):
    """Password change with a success flash message."""

    form_class = PasswordChangeForm
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('accounts:password_change_done')

    def form_valid(self, form):
        messages.success(self.request, 'Your password was successfully updated!')
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _record_login_ip(request, user: User) -> None:
    """Persist the user's login IP for basic audit purposes."""
    ip = _get_client_ip(request)
    if ip:
        User.objects.filter(pk=user.pk).update(last_login_ip=ip)


def _get_client_ip(request) -> str | None:
    """Extract the real client IP, respecting reverse-proxy headers."""
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')