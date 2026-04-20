from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.utils import timezone
from .models import Order, Client
from .services import (
    MarketplaceFinancePostingError,
    mark_order_finance_sync_failed,
    post_order_payment_to_finance,
    reset_order_finance_sync,
    reverse_order_payment_in_finance,
    set_order_finance_sync_error,
)


def company_admin_required(view_func):
    """Decorator to require user to be company admin"""
    from functools import wraps
    
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please login to continue.')
            return redirect('accounts:company_login')
        
        if not request.user.is_company_admin:
            messages.error(request, 'Only company administrators can access this page.')
            return redirect('core:dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@company_admin_required
def admin_order_dashboard(request):
    """Order management dashboard for company admins"""
    company = request.user.company
    
    # Get all orders for this company
    orders = Order.objects.filter(company=company).select_related('client')
    
    # Statistics
    total_orders = orders.count()
    pending_orders = orders.filter(status='pending').count()
    confirmed_orders = orders.filter(status='confirmed').count()
    shipped_orders = orders.filter(status='shipped').count()
    delivered_orders = orders.filter(status='delivered').count()
    
    total_revenue = orders.filter(payment_status='paid').aggregate(
        total=Sum('total')
    )['total'] or 0
    
    pending_revenue = orders.filter(
        status__in=['pending', 'confirmed'],
        payment_status='pending'
    ).aggregate(total=Sum('total'))['total'] or 0
    
    # Recent orders
    recent_orders = orders.order_by('-created_at')[:10]
    
    # Pending orders (need attention)
    pending_order_list = orders.filter(status='pending').order_by('-created_at')
    
    context = {
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'confirmed_orders': confirmed_orders,
        'shipped_orders': shipped_orders,
        'delivered_orders': delivered_orders,
        'total_revenue': total_revenue,
        'pending_revenue': pending_revenue,
        'recent_orders': recent_orders,
        'pending_order_list': pending_order_list,
    }
    
    return render(request, 'marketplace/admin/order_dashboard.html', context)


@login_required
@company_admin_required
def admin_order_list(request):
    """List all orders with filters"""
    company = request.user.company
    
    # Get orders for this company
    orders = Order.objects.filter(
        company=company
    ).select_related('client').order_by('-created_at')
    
    # Apply filters
    status = request.GET.get('status', '')
    if status:
        orders = orders.filter(status=status)
    
    payment_status = request.GET.get('payment_status', '')
    if payment_status:
        orders = orders.filter(payment_status=payment_status)
    
    # Search
    query = request.GET.get('q', '').strip()
    if query:
        orders = orders.filter(
            Q(order_number__icontains=query) |
            Q(client__email__icontains=query) |
            Q(client__first_name__icontains=query) |
            Q(client__last_name__icontains=query)
        )
    
    context = {
        'orders': orders,
        'query': query,
        'selected_status': status,
        'selected_payment_status': payment_status,
        'STATUS_CHOICES': Order.STATUS_CHOICES,
        'PAYMENT_STATUS_CHOICES': Order.PAYMENT_STATUS_CHOICES,
    }
    
    return render(request, 'marketplace/admin/order_list.html', context)


@login_required
@company_admin_required
def admin_order_detail(request, pk):
    """View and manage single order"""
    company = request.user.company
    order = get_object_or_404(Order, pk=pk, company=company)
    
    context = {
        'order': order,
    }
    
    return render(request, 'marketplace/admin/order_detail.html', context)


@login_required
@company_admin_required
def admin_order_confirm(request, pk):
    """Confirm an order"""
    company = request.user.company
    order = get_object_or_404(Order, pk=pk, company=company)
    
    if order.status != 'pending':
        messages.warning(request, f'Order is already {order.get_status_display()}')
        return redirect('marketplace:admin_order_detail', pk=pk)
    
    if request.method == 'POST':
        order.status = 'confirmed'
        order.confirmed_at = timezone.now()
        order.save()
        
        messages.success(request, f'Order #{order.order_number} confirmed successfully!')
        
        # TODO: Send email to client
        # send_order_confirmation_email(order)
        
        return redirect('marketplace:admin_order_detail', pk=pk)
    
    return render(request, 'marketplace/admin/order_confirm.html', {'order': order})


@login_required
@company_admin_required
def admin_order_ship(request, pk):
    """Mark order as shipped"""
    company = request.user.company
    order = get_object_or_404(Order, pk=pk, company=company)
    
    if order.status not in ['confirmed', 'processing']:
        messages.warning(request, 'Order must be confirmed before shipping')
        return redirect('marketplace:admin_order_detail', pk=pk)
    
    if request.method == 'POST':
        tracking_number = request.POST.get('tracking_number', '')
        
        order.status = 'shipped'
        order.shipped_at = timezone.now()
        if tracking_number:
            order.notes = f"{order.notes}\nTracking: {tracking_number}".strip()
        order.save()
        
        messages.success(request, f'Order #{order.order_number} marked as shipped!')
        
        # TODO: Send shipping notification email
        # send_shipping_notification_email(order, tracking_number)
        
        return redirect('marketplace:admin_order_detail', pk=pk)
    
    return render(request, 'marketplace/admin/order_ship.html', {'order': order})


@login_required
@company_admin_required
def admin_order_deliver(request, pk):
    """Mark order as delivered"""
    company = request.user.company
    order = get_object_or_404(Order, pk=pk, company=company)
    
    if order.status != 'shipped':
        messages.warning(request, 'Order must be shipped before marking as delivered')
        return redirect('marketplace:admin_order_detail', pk=pk)
    
    if request.method == 'POST':
        order.status = 'delivered'
        order.delivered_at = timezone.now()
        order.save()
        
        messages.success(request, f'Order #{order.order_number} marked as delivered!')
        
        return redirect('marketplace:admin_order_detail', pk=pk)
    
    return render(request, 'marketplace/admin/order_deliver.html', {'order': order})


@login_required
@company_admin_required
def admin_order_cancel(request, pk):
    """Cancel an order and restore stock."""
    company = request.user.company
    order = get_object_or_404(Order, pk=pk, company=company)
    
    if order.status in ['delivered', 'cancelled']:
        messages.warning(request, 'Cannot cancel this order')
        return redirect('marketplace:admin_order_detail', pk=pk)
    
    if request.method == 'POST':
        from django.db import transaction as db_transaction
        from inventory.models import StockTransaction
        from django.db.models import F
        
        try:
            with db_transaction.atomic():
                # Restore stock quantities for this company's products only
                restored_items = 0
                for item in order.items.select_related('stock'):
                    stock = item.stock
                    stock.quantity = F('quantity') + item.quantity
                    stock.save()
                    
                    # Create reversal transaction
                    StockTransaction.objects.create(
                        company=company,
                        stock=stock,
                        transaction_type='in',
                        quantity=item.quantity,
                        remarks=f'Order #{order.order_number} cancelled - stock restored',
                        user=request.user
                    )
                    restored_items += 1
                
                if restored_items > 0:
                    if order.payment_status == 'paid' and order.finance_journal_entry_id:
                        reverse_order_payment_in_finance(
                            order,
                            user=request.user,
                            reason='order cancelled',
                        )
                        order.payment_status = 'refunded'
                    order.status = 'cancelled'
                    order.save(update_fields=['status', 'payment_status', 'updated_at'])
                    messages.success(request, f'Order #{order.order_number} cancelled and stock restored!')
                else:
                    messages.warning(request, 'No items were restored for this order.')
                
        except Exception as e:
            messages.error(request, f'Error processing cancellation: {str(e)}')
        
        return redirect('marketplace:admin_order_detail', pk=pk)
    
    return render(request, 'marketplace/admin/order_cancel.html', {'order': order})


@login_required
@company_admin_required
def admin_order_update_payment(request, pk):
    """Update payment status"""
    company = request.user.company
    order = get_object_or_404(Order, pk=pk, company=company)
    
    if request.method == 'POST':
        payment_status = request.POST.get('payment_status')
        
        if payment_status in dict(Order.PAYMENT_STATUS_CHOICES):
            if order.finance_reversal_journal_entry_id:
                if payment_status == 'refunded':
                    messages.success(request, 'Payment status remains Refunded; finance reversal entry already exists.')
                else:
                    messages.error(
                        request,
                        'This order has already been reversed in finance and cannot move to another payment state.'
                    )
                return redirect('marketplace:admin_order_detail', pk=pk)

            if payment_status == 'paid':
                order.payment_status = payment_status
                order.save(update_fields=['payment_status', 'updated_at'])
                try:
                    _, created = post_order_payment_to_finance(order, user=request.user)
                    if created:
                        messages.success(
                            request,
                            f'Payment status updated to {order.get_payment_status_display()} and posted to finance.'
                        )
                    else:
                        messages.success(
                            request,
                            f'Payment status remains {order.get_payment_status_display()}; finance entry already exists.'
                        )
                except MarketplaceFinancePostingError as exc:
                    if order.finance_journal_entry_id:
                        set_order_finance_sync_error(order, str(exc))
                    else:
                        mark_order_finance_sync_failed(order, str(exc))
                    messages.warning(
                        request,
                        f'Payment status updated to {order.get_payment_status_display()}, but finance posting failed: {exc}'
                    )
            elif payment_status == 'refunded':
                if order.payment_status != 'paid':
                    messages.error(request, 'Only paid orders can be marked as refunded.')
                    return redirect('marketplace:admin_order_detail', pk=pk)
                if not order.finance_journal_entry_id:
                    messages.error(
                        request,
                        'This order has no finance posting yet, so it cannot be refunded through the reversal flow.'
                    )
                    return redirect('marketplace:admin_order_detail', pk=pk)

                try:
                    _, created = reverse_order_payment_in_finance(
                        order,
                        user=request.user,
                        reason='payment refunded',
                    )
                    order.payment_status = 'refunded'
                    order.save(update_fields=['payment_status', 'updated_at'])
                    if created:
                        messages.success(
                            request,
                            'Payment status updated to Refunded and reversal entry posted to finance.'
                        )
                    else:
                        messages.success(
                            request,
                            'Payment status remains Refunded; finance reversal entry already exists.'
                        )
                except MarketplaceFinancePostingError as exc:
                    set_order_finance_sync_error(order, str(exc))
                    messages.warning(
                        request,
                        f'Unable to reverse the finance posting for this refund: {exc}'
                    )
            else:
                if order.finance_journal_entry_id and not order.finance_reversal_journal_entry_id:
                    messages.error(
                        request,
                        'This order is already posted to finance. Use Refunded to create a reversal entry.'
                    )
                    return redirect('marketplace:admin_order_detail', pk=pk)

                order.payment_status = payment_status
                order.save(update_fields=['payment_status', 'updated_at'])
                reset_order_finance_sync(order)
                messages.success(request, f'Payment status updated to {order.get_payment_status_display()}')
        
        return redirect('marketplace:admin_order_detail', pk=pk)
    
    return redirect('marketplace:admin_order_detail', pk=pk)


@login_required
@company_admin_required
def admin_client_list(request):
    """View all clients who have ordered from this company"""
    company = request.user.company
    clients = Client.objects.filter(
        orders__company=company
    ).distinct().order_by('-created_at')
    
    # Search
    query = request.GET.get('q', '').strip()
    if query:
        clients = clients.filter(
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )
    
    context = {
        'clients': clients,
        'query': query,
    }
    
    return render(request, 'marketplace/admin/client_list.html', context)
