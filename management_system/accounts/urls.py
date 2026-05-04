from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from django.urls import path, reverse_lazy

app_name = 'accounts'

urlpatterns = [
    # Login/Logout
    path('', views.company_login, name='company_login'),
    path('login/', views.company_login, name='company_login'),
    path('logout/', views.custom_logout, name='logout'),
    
    # Registration
    path('register/company/', views.company_register, name='company_register'),
    path('register/user/', views.user_register, name='user_register'),
    
    # Profile
    path('profile/company/', views.company_profile, name='company_profile'),
    path('profile/user/', views.user_profile, name='user_profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    
    # Password management
    path('password-change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('password-change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='accounts/password_change_done.html'
    ), name='password_change_done'),
    
    # Password reset (if needed)
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='accounts/password_reset.html',
        email_template_name='accounts/password_reset_email.html',
        subject_template_name='accounts/password_reset_subject.txt',
        success_url=reverse_lazy('accounts:password_reset_done')
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/password_reset_done.html'
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='accounts/password_reset_confirm.html'
    ), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html'
    ), name='password_reset_complete'),

    path('language/', views.set_language, name='set_language'),
]