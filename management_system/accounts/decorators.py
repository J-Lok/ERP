from functools import wraps
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect


def role_required(*allowed_roles, redirect_url: str = 'core:dashboard'):
    """
    Restrict a view to users whose role is in ``allowed_roles``.
    Superusers always pass.

    Usage:
        @role_required('admin', 'hr_manager')
        def my_view(request): ...

        # Or with a list:
        @role_required(['admin', 'accountant'])
        def finance_view(request): ...

        # Single role:
        @role_required('admin')
        def admin_view(request): ...

        # Custom redirect on denial:
        @role_required('admin', redirect_url='accounts:company_login')
        def sensitive_view(request): ...
    """
    # Flatten in case someone passes a list by mistake
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
                f'Required role(s): {", ".join(sorted(roles))}.'
            )
            return redirect(redirect_url)

        return wrapper
    return decorator


def company_admin_required(view_func=None, *, redirect_url: str = 'core:dashboard'):
    """
    Shortcut decorator: only company admins (or superusers) may access the view.

    Usage:
        @company_admin_required
        def admin_only_view(request): ...
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

    # Allow use with or without parentheses: @company_admin_required or @company_admin_required()
    if view_func is not None:
        return decorator(view_func)
    return decorator