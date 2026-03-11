from django.utils.deprecation import MiddlewareMixin


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