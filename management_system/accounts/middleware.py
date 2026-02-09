from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.urls import reverse

class CompanyContextMiddleware(MiddlewareMixin):
    """Middleware to add company context to all requests"""
    
    def process_request(self, request):
        if request.user.is_authenticated:
            # Store company in request for easy access
            request.company = request.user.company