"""
accounts/permissions.py

Single source of truth for role-based access control across all apps.

Role hierarchy (highest → lowest):
    superuser  — Django superuser, bypasses all checks
    admin      — Full company admin
    manager    — Full access to all modules (departments, employees, projects, finance, inventory, HR, CRM, meetings, marketplace)
    hr_manager — HR management
    accountant — Finance read/write
    secretary  — CRM, scheduling
    stock_manager — Inventory management
    employee   — Self-service only
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

# ---------------------------------------------------------------------------
# Role group constants
# ---------------------------------------------------------------------------

# Employees app
EMPLOYEE_VIEW_ROLES   = ('admin', 'hr_manager', 'manager', 'accountant', 'secretary', 'stock_manager', 'employee')
EMPLOYEE_WRITE_ROLES  = ('admin', 'hr_manager', 'manager')
EMPLOYEE_DELETE_ROLES = ('admin', 'manager')
EMPLOYEE_EXPORT_ROLES = ('admin', 'hr_manager', 'accountant', 'manager')

# Departments
DEPARTMENT_WRITE_ROLES  = ('admin', 'hr_manager', 'manager')
DEPARTMENT_DELETE_ROLES = ('admin', 'manager')

# Projects app
PROJECT_VIEW_ROLES   = ('admin', 'manager', 'hr_manager', 'accountant', 'secretary', 'stock_manager', 'employee')
PROJECT_WRITE_ROLES  = ('admin', 'manager', 'hr_manager')
PROJECT_DELETE_ROLES = ('admin', 'manager')
PROJECT_REPORT_ROLES = ('admin', 'manager', 'accountant')

# Tasks (sous-tâches) — broader, team members should be able to update their tasks
TASK_WRITE_ROLES  = ('admin', 'manager', 'hr_manager', 'secretary', 'stock_manager', 'employee')
TASK_DELETE_ROLES = ('admin', 'manager')

# Inventory app
INVENTORY_VIEW_ROLES    = ('admin', 'manager', 'hr_manager', 'accountant', 'secretary', 'stock_manager', 'employee')
INVENTORY_WRITE_ROLES   = ('admin', 'stock_manager', 'manager')
INVENTORY_MANAGE_ROLES  = ('admin', 'manager', 'stock_manager')
INVENTORY_REPORT_ROLES  = ('admin', 'manager', 'accountant', 'stock_manager')

# Finance app (defined here for completeness; also used in finance/views.py)
FINANCE_ROLES = ('admin', 'accountant', 'manager')

# HR app
HR_ROLES           = ('admin', 'hr_manager', 'manager')
LEAVE_SUBMIT_ROLES = ('admin', 'hr_manager', 'manager', 'secretary', 'accountant', 'stock_manager', 'employee')

# CRM app
CRM_ROLES = ('admin', 'manager', 'secretary')

# Meetings app
MEETINGS_VIEW_ROLES   = ('admin', 'hr_manager', 'manager', 'secretary', 'accountant', 'employee')
MEETINGS_WRITE_ROLES  = ('admin', 'hr_manager', 'manager', 'secretary')
MEETINGS_DELETE_ROLES = ('admin', 'manager')
MEETINGS_REPORT_ROLES = ('admin', 'manager', 'accountant')

# Marketplace admin
MARKETPLACE_ADMIN_ROLES = ('admin', 'manager')

# Dashboard sections — which roles see which stat blocks
DASHBOARD_FINANCE_ROLES  = ('admin', 'accountant', 'manager')
DASHBOARD_HR_ROLES       = ('admin', 'hr_manager', 'manager')
DASHBOARD_EMPLOYEE_ROLES = ('admin', 'hr_manager', 'manager', 'accountant')


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def role_required(*allowed_roles, redirect_url: str = 'core:dashboard'):
    """
    Restrict a view to users whose role is in ``allowed_roles``.
    Superusers always pass.

    Usage:
        @role_required('admin', 'hr_manager')
        def my_view(request): ...

        @role_required(*EMPLOYEE_WRITE_ROLES)
        def create_employee(request): ...
    """
    # Flatten in case a list/tuple is passed by mistake
    flattened = []
    for role in allowed_roles:
        if isinstance(role, (list, tuple)):
            flattened.extend(role)
        else:
            flattened.append(role)
    roles = set(flattened)

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.is_superuser or request.user.role in roles:
                return view_func(request, *args, **kwargs)
            messages.error(
                request,
                'You do not have permission to access that page. '
                f'Required role(s): {", ".join(sorted(roles))}.',
            )
            return redirect(redirect_url)
        return wrapper
    return decorator


def company_admin_required(view_func=None, *, redirect_url: str = 'core:dashboard'):
    """
    Only company admins (or superusers) may access the view.

    Usage:
        @company_admin_required
        def admin_view(request): ...

        @company_admin_required(redirect_url='accounts:company_login')
        def sensitive_view(request): ...
    """
    def decorator(func):
        @wraps(func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.is_superuser or request.user.is_company_admin:
                return func(request, *args, **kwargs)
            messages.error(request, 'Only company administrators can access this page.')
            return redirect(redirect_url)
        return wrapper

    if view_func is not None:
        return decorator(view_func)
    return decorator