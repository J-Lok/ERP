def company_context(request):
    company = None
    is_company_admin = False

    user = getattr(request, 'user', None)

    if user and user.is_authenticated:
        company = user.company
        is_company_admin = user.is_company_admin

    return {
        'company': company,
        'is_company_admin': is_company_admin,
    }
