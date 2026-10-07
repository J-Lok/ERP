from decimal import Decimal, InvalidOperation

from django.utils.http import url_has_allowed_host_and_scheme


class CurrencyFieldsMixin:
    """
    Mix into a ModelForm whose Meta.model stores some fields in USD, to show
    and accept them in the company's display currency instead.

    Usage — the form must already set self.company (same convention as every
    other company-scoped form in this app):

        class StockForm(CurrencyFieldsMixin, forms.ModelForm):
            currency_fields = ('cost_price', 'selling_price')

            def __init__(self, *args, company=None, **kwargs):
                self.company = company
                super().__init__(*args, **kwargs)
                self._convert_currency_fields_to_display()

            def clean(self):
                cleaned_data = super().clean()
                return self._convert_currency_fields_to_usd(cleaned_data)

    Every amount is stored in USD in the database — this mixin is the one
    place that converts it, at the form boundary, so neither the model nor
    any view needs to know about the company's currency.
    """

    currency_fields: tuple = ()

    def _convert_currency_fields_to_display(self) -> None:
        """Call after super().__init__() on a GET (unbound) form — overrides
        the USD-based initial values ModelForm just built from the instance
        with their equivalent in the company's display currency."""
        if not self.company or self.is_bound:
            return
        for field_name in self.currency_fields:
            usd_value = self.initial.get(field_name)
            if usd_value is None and self.instance and self.instance.pk:
                usd_value = getattr(self.instance, field_name, None)
            if usd_value is not None:
                converted = self.company.to_display_currency(usd_value)
                try:
                    converted = converted.quantize(Decimal('0.01'))
                except (AttributeError, InvalidOperation):
                    pass
                self.initial[field_name] = converted

    def _convert_currency_fields_to_usd(self, cleaned_data: dict) -> dict:
        """Call from clean() — converts whatever was typed in the company's
        display currency back to USD before it reaches instance/save()."""
        if self.company:
            for field_name in self.currency_fields:
                value = cleaned_data.get(field_name)
                if value is not None:
                    cleaned_data[field_name] = self.company.from_display_currency(value)
        return cleaned_data


def generate_company_code(company, model, field_name: str, infix: str, width: int = 4) -> str:
    """
    Next sequential company-scoped code, e.g. 'ACM-ITM-0004'.

    One shared convention for every user-facing code that must always be
    system-generated rather than typed (item codes, invoice numbers, employee
    IDs, ...): '{company domain prefix}-{infix}-{sequential number}'.
    """
    prefix = f'{company.domain.upper()[:3]}-{infix}'

    last = (
        model.objects
        .filter(company=company)
        .order_by('-id')
        .values_list(field_name, flat=True)
        .first()
    )
    next_num = 1
    if last:
        try:
            next_num = int(last.rsplit('-', 1)[-1]) + 1
        except (ValueError, IndexError):
            next_num = model.objects.filter(company=company).count() + 1

    return f'{prefix}-{next_num:0{width}d}'


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
