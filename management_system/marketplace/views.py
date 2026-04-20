from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, F,Count, Sum
from django.db import transaction as db_transaction
from django.utils import timezone
from functools import wraps

from .models import Client, Cart, CartItem, Order, OrderItem, Wishlist, WishlistItem
from .forms import ClientRegistrationForm, ClientLoginForm, ClientProfileForm, CheckoutForm, AddToCartForm
from inventory.models import Stock, StockCategory, StockTransaction
from accounts.models import Company
from .services import reverse_order_payment_in_finance


def get_cart_company(cart):
    """Return the single company represented in a cart, if any."""
    first_item = cart.items.select_related('stock__company').first()
    return first_item.stock.company if first_item else None


# Client Authentication Decorator
def client_login_required(view_func):
    """Decorator to require client login"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if 'client_id' not in request.session:
            messages.warning(request, 'Please login to continue.')
            return redirect('marketplace:client_login')
        
        try:
            client = Client.objects.get(id=request.session['client_id'], is_active=True)
            request.client = client
        except Client.DoesNotExist:
            del request.session['client_id']
            messages.error(request, 'Session expired. Please login again.')
            return redirect('marketplace:client_login')
        
        return view_func(request, *args, **kwargs)
    return wrapper


# Authentication Views
def client_login(request):
    """Client login view"""
    if 'client_id' in request.session:
        return redirect('marketplace:shop')

    if request.method == 'POST':
        form = ClientLoginForm(request.POST)
        if form.is_valid():
            client = form.cleaned_data['client']
            request.session['client_id'] = client.id
            messages.success(request, f'Welcome back, {client.first_name}!')
            return redirect('marketplace:shop')
    else:
        form = ClientLoginForm()
    
    return render(request, 'marketplace/client_login.html', {
        'form': form,
        'title': 'Client Login',
    })


def client_register(request):
    """Client registration view"""
    if 'client_id' in request.session:
        return redirect('marketplace:shop')

    if request.method == 'POST':
        form = ClientRegistrationForm(request.POST)
        if form.is_valid():
            client = form.save()
            messages.success(request, f'Account created successfully! Welcome, {client.first_name}!')
            # Auto-login after registration
            request.session['client_id'] = client.id
            return redirect('marketplace:shop')
    else:
        form = ClientRegistrationForm()
    
    return render(request, 'marketplace/client_register.html', {
        'form': form,
        'title': 'Create Account',
    })


@client_login_required
def client_logout(request):
    """Client logout view"""
    if 'client_id' in request.session:
        del request.session['client_id']
    if 'client_company_id' in request.session:
        del request.session['client_company_id']
    
    messages.success(request, 'You have been logged out successfully.')
    return redirect('marketplace:client_login')


# Shop Views
def shop(request):
    """Main shop view - display available products (public view, login required for checkout)"""
    client = None
    company = None

    # determine company selection from GET param
    domain_param = request.GET.get('company')
    if domain_param:
        try:
            company = Company.objects.get(domain=domain_param, is_active=True)
            request.session['marketplace_company'] = domain_param
        except Company.DoesNotExist:
            messages.error(request, 'Selected shop does not exist.')

    # Get client if logged in
    if 'client_id' in request.session:
        try:
            client = Client.objects.get(id=request.session['client_id'], is_active=True)
            request.client = client
        except Client.DoesNotExist:
            del request.session['client_id']

    # if no explicit company yet, look in session
    if not company and 'marketplace_company' in request.session:
        try:
            company = Company.objects.get(domain=request.session['marketplace_company'], is_active=True)
        except Company.DoesNotExist:
            del request.session['marketplace_company']
            company = None

    # Get all active companies for the dropdown menu
    all_companies = Company.objects.filter(is_active=True).order_by('name')
    
    # fallback to first company with stock if no company selected
    companies_with_stock = Company.objects.filter(
        stocks__quantity__gt=0
    ).distinct().order_by('name')
    if not company and companies_with_stock.exists():
        company = companies_with_stock.first()
    
    # If still no company but companies exist, use first active company
    if not company and all_companies.exists():
        company = all_companies.first()

    if not company:
        messages.info(request, 'No shops available currently.')
        return render(request, 'marketplace/shop.html', {'stocks': [], 'is_logged_in': False, 'companies': all_companies})
    
    # Get available stock items from this company
    stocks = Stock.objects.filter(
        company=company,
        quantity__gt=0,
        is_marketplace_visible=True
    ).select_related('category').order_by('-created_at')
    
    # Apply search
    query = request.GET.get('q', '').strip()
    if query:
        stocks = stocks.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(item_code__icontains=query)
        )
    
    # Apply category filter
    category_id = request.GET.get('category')
    if category_id:
        stocks = stocks.filter(category_id=category_id)
    
    # Get categories for filter
    categories = StockCategory.objects.filter(company=company).order_by('name')
    
    # Get cart count if logged in
    cart_count = 0
    if client:
        cart = Cart.objects.filter(client=client).first()
        cart_count = cart.total_items if cart else 0
    
    context = {
        'stocks': stocks,
        'categories': categories,
        'company': company,
        'companies': all_companies,
        'query': query,
        'selected_category': category_id,
        'cart_count': cart_count,
        'is_logged_in': client is not None,
    }
    
    return render(request, 'marketplace/shop.html', context)


def product_detail(request, pk):
    """Product detail view (public view, login required for add to cart)"""
    client = None
    
    # Get client if logged in
    if 'client_id' in request.session:
        try:
            client = Client.objects.get(id=request.session['client_id'], is_active=True)
            request.client = client
        except Client.DoesNotExist:
            del request.session['client_id']
    
    stock = get_object_or_404(Stock, pk=pk)
    
    # Check if in wishlist (only if logged in)
    in_wishlist = False
    if client:
        wishlist = Wishlist.objects.filter(client=client).first()
        if wishlist:
            in_wishlist = WishlistItem.objects.filter(wishlist=wishlist, stock=stock).exists()
    
    # Check if client can purchase this product (clients can buy from any company now)
    can_purchase = client is not None
    
    context = {
        'stock': stock,
        'in_wishlist': in_wishlist,
        'is_logged_in': client is not None,
        'can_purchase': can_purchase,
    }
    
    return render(request, 'marketplace/product_detail.html', context)


@client_login_required
def shop_by_category(request, category_id):
    """Filter products by category"""
    return redirect('marketplace:shop' + f'?category={category_id}')


# Cart Views
@client_login_required
def view_cart(request):
    """View shopping cart"""
    client = request.client
    cart, created = Cart.objects.get_or_create(client=client)
    cart_items = cart.items.all().select_related('stock')
    
    context = {
        'cart': cart,
        'cart_items': cart_items,
    }
    
    return render(request, 'marketplace/cart.html', context)


@client_login_required
def add_to_cart(request, stock_id):
    """Add item to cart"""
    client = request.client
    stock = get_object_or_404(Stock, pk=stock_id)
    
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        
        # Check stock availability
        if stock.quantity < quantity:
            messages.error(request, f'Only {stock.quantity} units available.')
            return redirect('marketplace:product_detail', pk=stock_id)
        
        cart, created = Cart.objects.get_or_create(client=client)
        cart_company = get_cart_company(cart)
        if cart_company and cart_company.id != stock.company_id:
            messages.error(
                request,
                f'Your cart already contains items from {cart_company.name}. '
                'Please clear the cart before adding products from another company.'
            )
            return redirect('marketplace:view_cart')
        
        # Check if item already in cart
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            stock=stock,
            defaults={'quantity': quantity}
        )
        
        if not created:
            # Update quantity
            new_quantity = cart_item.quantity + quantity
            if new_quantity > stock.quantity:
                messages.error(request, f'Only {stock.quantity} units available.')
                return redirect('marketplace:view_cart')
            cart_item.quantity = new_quantity
            cart_item.save()
            messages.success(request, f'Updated {stock.name} quantity to {new_quantity}')
        else:
            messages.success(request, f'Added {stock.name} to cart')
        
        return redirect('marketplace:view_cart')
    
    return redirect('marketplace:shop')


@client_login_required
def update_cart_item(request, item_id):
    """Update cart item quantity"""
    client = request.client
    cart_item = get_object_or_404(CartItem, pk=item_id, cart__client=client)
    
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        
        if quantity <= 0:
            cart_item.delete()
            messages.success(request, 'Item removed from cart')
        elif quantity > cart_item.stock.quantity:
            messages.error(request, f'Only {cart_item.stock.quantity} units available')
        else:
            cart_item.quantity = quantity
            cart_item.save()
            messages.success(request, 'Cart updated')
    
    return redirect('marketplace:view_cart')


@client_login_required
def remove_from_cart(request, item_id):
    """Remove item from cart"""
    client = request.client
    cart_item = get_object_or_404(CartItem, pk=item_id, cart__client=client)
    
    if request.method == 'POST':
        item_name = cart_item.stock.name
        cart_item.delete()
        messages.success(request, f'Removed {item_name} from cart')
    
    return redirect('marketplace:view_cart')


@client_login_required
def clear_cart(request):
    """Clear all items from cart"""
    client = request.client
    
    if request.method == 'POST':
        cart = Cart.objects.filter(client=client).first()
        if cart:
            cart.items.all().delete()
            messages.success(request, 'Cart cleared')
    
    return redirect('marketplace:view_cart')


# Wishlist Views
@client_login_required
def view_wishlist(request):
    """View wishlist"""
    client = request.client
    wishlist, created = Wishlist.objects.get_or_create(client=client)
    items = wishlist.items.all().select_related('stock')
    
    context = {
        'wishlist': wishlist,
        'items': items,
    }
    
    return render(request, 'marketplace/wishlist.html', context)


@client_login_required
def add_to_wishlist(request, stock_id):
    """Add item to wishlist"""
    client = request.client
    stock = get_object_or_404(Stock, pk=stock_id, is_marketplace_visible=True)
    
    if request.method == 'POST':
        wishlist, created = Wishlist.objects.get_or_create(client=client)
        
        item, created = WishlistItem.objects.get_or_create(
            wishlist=wishlist,
            stock=stock
        )
        
        if created:
            messages.success(request, f'Added {stock.name} to wishlist')
        else:
            messages.info(request, f'{stock.name} is already in your wishlist')
        
        return redirect(request.META.get('HTTP_REFERER', 'marketplace:shop'))
    
    return redirect('marketplace:shop')


@client_login_required
def remove_from_wishlist(request, item_id):
    """Remove item from wishlist"""
    client = request.client
    item = get_object_or_404(WishlistItem, pk=item_id, wishlist__client=client)
    
    if request.method == 'POST':
        item_name = item.stock.name
        item.delete()
        messages.success(request, f'Removed {item_name} from wishlist')
    
    return redirect('marketplace:view_wishlist')


# Checkout & Orders
@client_login_required
def checkout(request):
    """Checkout process"""
    client = request.client
    cart = Cart.objects.filter(client=client).first()
    
    if not cart or not cart.items.exists():
        messages.warning(request, 'Your cart is empty')
        return redirect('marketplace:shop')

    cart_company = get_cart_company(cart)
    if not cart_company:
        messages.error(request, 'Unable to determine the company for this cart.')
        return redirect('marketplace:view_cart')

    mixed_company_items = cart.items.exclude(stock__company=cart_company)
    if mixed_company_items.exists():
        messages.error(
            request,
            'Your cart contains products from multiple companies. '
            'Please keep one company per order.'
        )
        return redirect('marketplace:view_cart')
    
    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                with db_transaction.atomic():
                    # Create order
                    order = form.save(commit=False)
                    order.client = client
                    order.company = cart_company
                    order.subtotal = cart.total_price
                    order.tax = 0  # Add tax calculation if needed
                    order.shipping = 0  # Add shipping calculation if needed
                    order.total = order.subtotal + order.tax + order.shipping
                    order.order_number = f"ORD-{timezone.now().strftime('%Y%m%d%H%M%S')}-{client.id}"
                    order.save()
                    
                    # Create order items and update stock
                    for cart_item in cart.items.select_related('stock', 'stock__company'):
                        # Check stock availability again
                        if cart_item.stock.quantity < cart_item.quantity:
                            raise Exception(f'Insufficient stock for {cart_item.stock.name}')
                        
                        # Create order item
                        OrderItem.objects.create(
                            order=order,
                            stock=cart_item.stock,
                            item_name=cart_item.stock.name,
                            item_code=cart_item.stock.item_code,
                            quantity=cart_item.quantity,
                            unit_price=cart_item.stock.selling_price,
                            subtotal=cart_item.subtotal
                        )
                        
                        # Update stock quantity
                        stock = cart_item.stock
                        stock.quantity = F('quantity') - cart_item.quantity
                        stock.save()
                        
                        # Create stock transaction
                        StockTransaction.objects.create(
                            company=stock.company,
                            stock=stock,
                            transaction_type='out',
                            quantity=cart_item.quantity,
                            remarks=f'Order #{order.order_number} by {client.get_full_name()}',
                            user=None  # No user for client orders
                        )
                    
                    # Clear cart
                    cart.items.all().delete()
                    
                    messages.success(request, f'Order placed successfully! Order number: {order.order_number}')
                    return redirect('marketplace:order_list')
                    
            except Exception as e:
                messages.error(request, f'Error processing order: {str(e)}')
                return redirect('marketplace:checkout')
    else:
        # Pre-fill with client info
        form = CheckoutForm(initial={
            'shipping_address': client.address,
            'shipping_city': client.city,
            'shipping_country': client.country,
            'shipping_phone': client.phone,
        })
    
    context = {
        'form': form,
        'cart': cart,
    }
    
    return render(request, 'marketplace/checkout.html', context)


@client_login_required
def order_list(request):
    """List all client orders"""
    client = request.client
    orders = Order.objects.filter(client=client).order_by('-created_at')
    
    # Get order statistics
    total_orders = orders.count()
    pending_orders = orders.filter(status='pending').count()
    confirmed_orders = orders.filter(status='confirmed').count()
    shipped_orders = orders.filter(status='shipped').count()
    delivered_orders = orders.filter(status='delivered').count()
    
    # Recent orders (last 5)
    recent_orders = orders[:5]
    
    context = {
        'orders': orders,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'confirmed_orders': confirmed_orders,
        'shipped_orders': shipped_orders,
        'delivered_orders': delivered_orders,
        'recent_orders': recent_orders,
    }
    
    return render(request, 'marketplace/order_list.html', context)


@client_login_required
def order_detail(request, pk):
    """View order details"""
    client = request.client
    order = get_object_or_404(Order, pk=pk, client=client)
    
    context = {
        'order': order,
    }
    
    return render(request, 'marketplace/order_detail.html', context)


@client_login_required
def cancel_order(request, pk):
    """Cancel an order"""
    client = request.client
    order = get_object_or_404(Order, pk=pk, client=client)
    
    if order.status not in ['pending', 'confirmed']:
        messages.error(request, 'This order cannot be cancelled')
        return redirect('marketplace:order_detail', pk=pk)
    
    if request.method == 'POST':
        try:
            with db_transaction.atomic():
                restored_items = 0
                for item in order.items.select_related('stock'):
                    stock = item.stock
                    stock.quantity = F('quantity') + item.quantity
                    stock.save()

                    StockTransaction.objects.create(
                        company=stock.company,
                        stock=stock,
                        transaction_type='in',
                        quantity=item.quantity,
                        remarks=f'Order #{order.order_number} cancelled by customer - stock restored',
                        user=None,
                    )
                    restored_items += 1

                if restored_items > 0 and order.payment_status == 'paid' and order.finance_journal_entry_id:
                    reverse_order_payment_in_finance(
                        order,
                        user=None,
                        reason='order cancelled by customer',
                    )
                    order.payment_status = 'refunded'

                order.status = 'cancelled'
                order.save(update_fields=['status', 'payment_status', 'updated_at'])
                messages.success(request, 'Order cancelled successfully')
        except Exception as exc:
            messages.error(request, f'Unable to cancel this order: {exc}')
        return redirect('marketplace:order_detail', pk=pk)
    
    return redirect('marketplace:order_detail', pk=pk)


# Profile Views
@client_login_required
def client_profile(request):
    """View client profile"""
    client = request.client
    
    # Get order statistics
    total_orders = Order.objects.filter(client=client).count()
    pending_orders = Order.objects.filter(client=client, status='pending').count()
    
    context = {
        'client': client,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
    }
    
    return render(request, 'marketplace/client_profile.html', context)


@client_login_required
def edit_client_profile(request):
    """Edit client profile"""
    client = request.client
    
    if request.method == 'POST':
        form = ClientProfileForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('marketplace:client_profile')
    else:
        form = ClientProfileForm(instance=client)
    
    context = {
        'form': form,
    }
    
    return render(request, 'marketplace/edit_client_profile.html', context)
