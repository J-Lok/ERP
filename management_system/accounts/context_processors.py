from django.http import HttpRequest


def company_context(request: HttpRequest) -> dict:
    """
    Inject company and role helpers into every template context.

    Available in all templates:
        {{ company }}            – Company instance or None
        {{ is_company_admin }}   – bool
        {{ user_role }}          – role string e.g. 'admin', 'manager'
        {{ user_has_role }}      – callable: {% if user_has_role 'admin' %}
    """
    company = None
    is_company_admin = False
    user_role = ''

    user = getattr(request, 'user', None)

    if user and user.is_authenticated:
        company = user.company
        is_company_admin = user.is_company_admin
        user_role = user.role

    return {
        'company': company,
        'is_company_admin': is_company_admin,
        'user_role': user_role,
    }