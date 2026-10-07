from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter(name='currency')
def currency(usd_amount, company):
    """
    Usage: {{ invoice.total|currency:company }}

    Every monetary field in the app is stored in USD. This converts it to
    `company`'s selected display currency (via its manually-set
    exchange_rate) and formats it with the currency symbol, e.g.
    "FCFA 60,000.00" or "$ 100.00". Renders '' if either side is missing,
    so a null amount or a None company (e.g. an order with no company yet)
    just shows nothing instead of raising.
    """
    if company is None:
        return ''
    try:
        converted = company.to_display_currency(Decimal(usd_amount or 0))
    except (InvalidOperation, TypeError):
        return ''
    return f'{company.currency_symbol} {converted:,.2f}'


@register.filter(name='to_currency')
def to_currency(usd_amount, company):
    """
    Usage: data-price="{{ stock.selling_price|to_currency:company }}"

    Same conversion as `currency`, but returns a bare number (no symbol, no
    thousands separator) — for embedding in a data attribute that
    client-side JS will parseFloat() and do further math on.
    """
    if company is None:
        return 0
    try:
        return company.to_display_currency(Decimal(usd_amount or 0))
    except (InvalidOperation, TypeError):
        return 0
