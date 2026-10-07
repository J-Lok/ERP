from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from accounts.permissions import (
    SUPPLIER_DELETE_ROLES,
    SUPPLIER_VIEW_ROLES,
    SUPPLIER_WRITE_ROLES,
    role_required,
)

from .forms import SupplierForm
from .models import Supplier

PAGE_SIZE = 25


def _paginate(qs, page_number, per_page=PAGE_SIZE):
    paginator = Paginator(qs, per_page)
    try:
        return paginator.page(page_number)
    except PageNotAnInteger:
        return paginator.page(1)
    except EmptyPage:
        return paginator.page(paginator.num_pages)


@role_required(*SUPPLIER_VIEW_ROLES)
def supplier_list(request):
    company = request.user.company
    qs = Supplier.objects.filter(company=company).annotate(
        item_total=Count('stock_items', distinct=True),
        invoice_total=Count('invoices', distinct=True),
    )

    query = request.GET.get('q', '').strip()
    if query:
        qs = qs.filter(
            Q(name__icontains=query)
            | Q(contact_person__icontains=query)
            | Q(email__icontains=query)
            | Q(phone__icontains=query)
        )

    status = request.GET.get('status', '')
    if status == 'active':
        qs = qs.filter(is_active=True)
    elif status == 'inactive':
        qs = qs.filter(is_active=False)

    stats = Supplier.objects.filter(company=company).aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(is_active=True)),
    )

    return render(request, 'suppliers/supplier_list.html', {
        'suppliers': _paginate(qs.order_by('name'), request.GET.get('page')),
        'query': query,
        'selected_status': status,
        'stats': stats,
    })


@role_required(*SUPPLIER_VIEW_ROLES)
def supplier_detail(request, pk):
    """Per-supplier dashboard: invoice count/totals, linked stock items."""
    company = request.user.company
    supplier = get_object_or_404(Supplier, pk=pk, company=company)

    invoices = supplier.invoices.order_by('-date')[:20]
    stock_items = supplier.stock_items.order_by('name')[:20]

    invoice_stats = supplier.invoices.aggregate(
        count=Count('id'),
        total=Sum('total'),
    )

    return render(request, 'suppliers/supplier_detail.html', {
        'supplier': supplier,
        'invoices': invoices,
        'stock_items': stock_items,
        'invoice_stats': invoice_stats,
    })


@role_required(*SUPPLIER_WRITE_ROLES)
@require_http_methods(['GET', 'POST'])
def supplier_create(request):
    company = request.user.company
    if request.method == 'POST':
        form = SupplierForm(request.POST, company=company)
        if form.is_valid():
            supplier = form.save()
            messages.success(request, f'Supplier "{supplier.name}" created.')
            return redirect('suppliers:supplier_detail', pk=supplier.pk)
    else:
        form = SupplierForm(company=company)
    return render(request, 'suppliers/supplier_form.html', {'form': form, 'title': 'Add Supplier'})


@role_required(*SUPPLIER_WRITE_ROLES)
@require_http_methods(['GET', 'POST'])
def supplier_edit(request, pk):
    company = request.user.company
    supplier = get_object_or_404(Supplier, pk=pk, company=company)
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Supplier "{supplier.name}" updated.')
            return redirect('suppliers:supplier_detail', pk=supplier.pk)
    else:
        form = SupplierForm(instance=supplier, company=company)
    return render(request, 'suppliers/supplier_form.html', {
        'form': form,
        'supplier': supplier,
        'title': 'Edit Supplier',
    })


@role_required(*SUPPLIER_DELETE_ROLES)
@require_http_methods(['GET', 'POST'])
def supplier_delete(request, pk):
    company = request.user.company
    supplier = get_object_or_404(Supplier, pk=pk, company=company)
    if request.method == 'POST':
        name = supplier.name
        supplier.delete()
        messages.success(request, f'Supplier "{name}" deleted.')
        return redirect('suppliers:supplier_list')
    return render(request, 'suppliers/supplier_confirm_delete.html', {'supplier': supplier})


@role_required(*SUPPLIER_WRITE_ROLES)
@require_http_methods(['POST'])
def supplier_quick_create(request):
    """AJAX endpoint — create a supplier inline from the stock item form."""
    company = request.user.company
    form = SupplierForm(request.POST, company=company)
    if form.is_valid():
        supplier = form.save()
        return JsonResponse({'success': True, 'id': supplier.id, 'name': supplier.name})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)
