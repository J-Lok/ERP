from django.db import transaction
from django.db.models import F
from inventory.models import Stock


class InsufficientStockError(Exception):
    """Raised when stock adjustment cannot be completed due to insufficient quantity."""
    pass


def adjust_stock(stock_id, delta):
    """
    Atomically adjust stock quantity using database row locking.

    Args:
        stock_id (int): Primary key of the Stock item.
        delta (int/float): Change in quantity (positive for restock/returns, negative for sales).

    Returns:
        Stock: Updated Stock instance.

    Raises:
        Stock.DoesNotExist: If stock item does not exist.
        InsufficientStockError: If delta is negative and resulting quantity would fall below 0.
    """
    with transaction.atomic():
        stock = Stock.objects.select_for_update().get(pk=stock_id)
        if delta < 0 and (stock.quantity + delta) < 0:
            raise InsufficientStockError(
                f"Insufficient stock for item '{stock.name}' (Code: {stock.item_code}). "
                f"Available: {stock.quantity}, Requested: {abs(delta)}"
            )
        stock.quantity = F('quantity') + delta
        stock.save(update_fields=['quantity'])
        stock.refresh_from_db()
        return stock


def marketplace_visible_stocks(company=None):
    """
    Return queryset of marketplace-visible stock items for active companies.
    """
    qs = Stock.objects.filter(
        company__is_active=True,
        is_marketplace_visible=True,
        quantity__gt=0,
    ).select_related('category', 'company')

    if company:
        qs = qs.filter(company=company)
    return qs
