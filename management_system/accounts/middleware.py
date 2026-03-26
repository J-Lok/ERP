from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.urls import reverse


class CompanyContextMiddleware(MiddlewareMixin):
    """
    Attach the authenticated user's company to every request object.

    Usage in views / templates:
        request.company  →  Company instance or None
    """

    def process_request(self, request) -> None:
        request.company = None

        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return

        # Use select_related to avoid an extra DB query if company fields
        # are accessed later in the same request cycle.
        if not hasattr(user, '_company_cached'):
            # company is a FK so it may already be cached by Django ORM;
            # guard prevents redundant attribute access on anonymous users.
            pass

        request.company = user.company


class RequireLoginMiddleware(MiddlewareMixin):
    """
    Enforce authentication for private ERP routes.

    Public endpoints (login/register/reset, marketplace, admin auth, static/media)
    remain accessible without Django user authentication.
    """

    def process_request(self, request):
        if request.user.is_authenticated:
            return None

        path = request.path

        public_prefixes = (
            '/admin/',
            '/marketplace/',
            '/static/',
            '/media/',
            '/password-reset/',
            '/reset/',
            '/register/',
        )
        public_exact_paths = (
            '/',
            '/login/',
        )

        if path in public_exact_paths or path.startswith(public_prefixes):
            return None

        login_url = reverse('accounts:company_login')
        return redirect(f'{login_url}?next={request.get_full_path()}')
