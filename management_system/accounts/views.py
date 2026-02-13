from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import PasswordChangeView
from django.contrib import messages
from django.urls import reverse_lazy
from django.core.exceptions import PermissionDenied

from .forms import (
    CompanyCreationForm, 
    UserRegistrationForm, 
    CompanyLoginForm,
    UserProfileForm,
    CompanyProfileForm
)
from .models import Company, User

def company_login(request):
    """Login with company domain"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        form = CompanyLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name}!')
            
            # Store company ID in session for middleware
            
            if user.company:
                 request.session['company_id'] = user.company.id

            # Redirect to next URL or dashboard
            next_url = request.GET.get('next', 'core:dashboard')
            return redirect(next_url)
    else:
        form = CompanyLoginForm()
    
    return render(request, 'accounts/company_login.html', {
        'form': form,
        'title': 'Company Login'
    })

def company_register(request):
    """Register a new company"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        form = CompanyCreationForm(request.POST)
        if form.is_valid():
            company = form.save()
            
            # Create company admin user
            user = User.objects.create_user(
                email=form.cleaned_data['admin_email'],
                password=form.cleaned_data['admin_password'],
                first_name=form.cleaned_data['admin_first_name'],
                last_name=form.cleaned_data['admin_last_name'],
                company=company,
                is_company_admin=True
            )
            
            messages.success(request, 
                f'Company "{company.name}" registered successfully! '
                f'You can now login with email: {user.email}'
            )
            return redirect('accounts:company_login')
    else:
        form = CompanyCreationForm()
    
    return render(request, 'accounts/company_register.html', {
        'form': form,
        'title': 'Register Company'
    })

def user_register(request):
    """Register a new user under an existing company"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Log the user in
            login(request, user)
            
            messages.success(request, 
                f'Welcome to {user.company.name}, {user.first_name}!'
            )
            return redirect('core:dashboard')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'accounts/user_register.html', {
        'form': form,
        'title': 'Join Company'
    })

@login_required
def custom_logout(request):
    """Custom logout view"""
    if request.user.is_authenticated:
        # Clear company session
        if 'company_id' in request.session:
            del request.session['company_id']
        
        logout(request)
        messages.success(request, 'You have been successfully logged out.')
    
    return redirect('accounts:company_login')

@login_required
def company_profile(request):
    """View and edit company profile (for company admins only)"""
    if not request.user.is_company_admin:
        raise PermissionDenied("Only company administrators can access this page.")
    
    company = request.user.company
    
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
        'title': 'Company Profile'
    })

@login_required
def user_profile(request):
    """View user profile"""
    user = request.user
    return render(request, 'accounts/user_profile.html', {
        'user': user,
        'title': 'My Profile'
    })

@login_required
def edit_profile(request):
    """Edit user profile"""
    user = request.user
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('accounts:user_profile')
    else:
        form = UserProfileForm(instance=user)
    
    return render(request, 'accounts/edit_profile.html', {
        'form': form,
        'title': 'Edit Profile'
    })

class CustomPasswordChangeView(PasswordChangeView):
    """Custom password change view"""
    form_class = PasswordChangeForm
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('accounts:password_change_done')
    
    def form_valid(self, form):
        messages.success(self.request, 'Your password was successfully updated!')
        return super().form_valid(form)