from functools import wraps
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required


def role_required(allowed_roles):
    """
    Decorator to restrict view access based on user role.
    
    Args:
        allowed_roles: List of role strings or single role string
        
    Example:
        @role_required(['admin', 'finance_manager'])
        def my_view(request):
            ...
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]
    
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role in allowed_roles or request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden(
                f"You do not have permission to access this page. Required roles: {', '.join(allowed_roles)}"
            )
        return wrapper
    return decorator
