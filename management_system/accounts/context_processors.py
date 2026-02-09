def company_context(request):
    """Add company to template context"""
    if request.user.is_authenticated:
        return {
            'company': request.user.company,
            'is_company_admin': request.user.is_company_admin,
        }
    return {}