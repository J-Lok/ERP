from django.db import models


class Supplier(models.Model):
    """A supplier/vendor the company buys from — stock items and purchase
    invoices both reference this, scoped per company."""

    company = models.ForeignKey(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='suppliers',
    )
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('company', 'name')]
        ordering = ['name']
        indexes = [
            models.Index(fields=['company', 'is_active']),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def item_count(self) -> int:
        return self.stock_items.count()

    @property
    def invoice_count(self) -> int:
        return self.invoices.count()

    @property
    def total_invoiced(self):
        from django.db.models import Sum
        return self.invoices.aggregate(total=Sum('total'))['total'] or 0

    @property
    def total_unpaid(self):
        from django.db.models import Sum
        return (
            self.invoices.exclude(status='paid').exclude(status='cancelled')
            .aggregate(total=Sum('total'))['total'] or 0
        )
