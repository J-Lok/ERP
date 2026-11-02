from .models import Client, Cart
from accounts.models import Company
from inventory.models import StockCategory


def marketplace_context(request):
    """
    Context processor for marketplace templates.
    Provides cart_count, marketplace_client, marketplace_company, and marketplace_categories.
    """
    client = None
    cart_count = 0
    client_id = request.session.get('client_id')

    if client_id:
        try:
            client = Client.objects.filter(id=client_id, is_active=True).first()
            if client:
                cart = Cart.objects.filter(client=client).first()
                if cart:
                    cart_count = cart.total_items
        except Exception:
            pass

    # Marketplace company from session or request
    mp_company = None
    domain = request.session.get('marketplace_company')
    if domain:
        try:
            mp_company = Company.objects.filter(domain=domain, is_active=True).first()
        except Exception:
            pass

    categories = []
    if mp_company:
        try:
            categories = StockCategory.objects.filter(company=mp_company).order_by('name')
        except Exception:
            pass

    return {
        'marketplace_client': client,
        'cart_count': cart_count,
        'marketplace_categories': categories,
        'marketplace_company': mp_company,
    }
