import logging
from datetime import timedelta
from typing import ClassVar

from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone, translation
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


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

        request.company = user.company

        # Activate the user's preferred language.
        lang = getattr(user, 'language', 'en') or 'en'
        translation.activate(lang)
        request.LANGUAGE_CODE = lang

        # Update last_seen at most once per minute to avoid a DB write on every request.
        # Wrapped in try/except so a pending migration never takes down the whole app.
        try:
            now = timezone.now()
            if not user.last_seen or (now - user.last_seen) > timedelta(seconds=60):
                type(user).objects.filter(pk=user.pk).update(last_seen=now)
                user.last_seen = now
        except Exception:
            logger.warning("Failed to update last_seen for user %s", user.pk, exc_info=True)


class RequireLoginMiddleware(MiddlewareMixin):
    """
    Enforce authentication for private ERP routes.

    Public endpoints (login/register/reset, public marketplace/shop, static/media)
    remain accessible without Django user authentication.
    """
    PUBLIC_URL_NAMES: ClassVar[set[str]] = {
        'company_login',
        'accept_invitation',
        'password_reset',
        'password_reset_done',
        'password_reset_confirm',
        'password_reset_complete',
        'shop',
        'company_shop',
        'product_detail',
        'shop_by_category',
        'view_cart',
        'add_to_cart',
        'update_cart_item',
        'remove_from_cart',
        'clear_cart',
        'view_wishlist',
        'add_to_wishlist',
        'remove_from_wishlist',
        'checkout',
        'order_list',
        'order_detail',
        'order_pdf',
        'order_print',
        'cancel_order',
        'payment_gateway',
        'request_return',
        'add_product_review',
        'client_login',
        'client_register',
        'client_logout',
        'client_profile',
        'edit_client_profile',
    }

    PUBLIC_PREFIXES = (
        '/admin/',
        '/static/',
        '/media/products/',
    )

    PUBLIC_EXACT_PATHS = (
        '/',
        '/login/',
    )

    def process_request(self, request):
        if request.user.is_authenticated:
            return None

        path = request.path

        if path in self.PUBLIC_EXACT_PATHS or path.startswith(self.PUBLIC_PREFIXES):
            return None

        # Try the path as given, then with a trailing slash appended — a
        # request for /le-paquebot (no slash, as people naturally type or
        # share it) doesn't resolve to any view on its own; only
        # /le-paquebot/ does. Without this, such requests skip straight to
        # the login redirect below instead of ever reaching Django's own
        # APPEND_SLASH handling (CommonMiddleware), which runs later and
        # would otherwise 301 them to the slashed URL.
        candidates = (path,) if path.endswith('/') else (path, path + '/')
        for candidate in candidates:
            try:
                match = resolve(candidate)
            except Resolver404:
                continue
            if match.url_name in self.PUBLIC_URL_NAMES and not candidate.startswith('/marketplace/admin/'):
                return None
            break

        login_url = reverse('accounts:company_login')
        return redirect(f'{login_url}?next={request.get_full_path()}')