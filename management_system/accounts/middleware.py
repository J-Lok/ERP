from django.utils.deprecation import MiddlewareMixin

class CompanyContextMiddleware(MiddlewareMixin):
    """Attach company to request if available"""

    def process_request(self, request):
        request.company = None

        user = getattr(request, 'user', None)

        if user and user.is_authenticated:
            request.company = user.company
