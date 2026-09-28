from django.utils.http import url_has_allowed_host_and_scheme


def safe_next_url(request, default_url, url_to_check=None, param_name='next'):
    """
    Validate and return a safe redirect URL to prevent open redirect vulnerabilities.

    Args:
        request: HttpRequest instance
        default_url (str): Fallback URL if 'next' parameter is unsafe or missing
        url_to_check (str, optional): Explicit URL string to validate (e.g. HTTP_REFERER)
        param_name (str): Parameter key to inspect in GET/POST (default: 'next')

    Returns:
        str: Validated safe URL string
    """
    next_url = url_to_check or request.POST.get(param_name) or request.GET.get(param_name)
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure()
    ):
        return next_url
    return default_url
