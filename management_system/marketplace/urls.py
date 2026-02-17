from django.urls import path
from . import views

app_name = 'marketplace'

urlpatterns = [
    # Auth
    path('', views.client_login, name='client_login'),
    path('login/', views.client_login, name='client_login'),
    path('register/', views.client_register, name='client_register'),
    path('logout/', views.client_logout, name='client_logout'),
    
    # Shop
    path('shop/', views.shop, name='shop'),
    path('shop/<int:pk>/', views.product_detail, name='product_detail'),
    path('shop/category/<int:category_id>/', views.shop_by_category, name='shop_by_category'),
    
    # Cart
    path('cart/', views.view_cart, name='view_cart'),
    path('cart/add/<int:stock_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/clear/', views.clear_cart, name='clear_cart'),
    
    # Wishlist
    path('wishlist/', views.view_wishlist, name='view_wishlist'),
    path('wishlist/add/<int:stock_id>/', views.add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/remove/<int:item_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),
    
    # Checkout & Orders
    path('checkout/', views.checkout, name='checkout'),
    path('orders/', views.order_list, name='order_list'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
    path('orders/<int:pk>/cancel/', views.cancel_order, name='cancel_order'),
    
    # Profile
    path('profile/', views.client_profile, name='client_profile'),
    path('profile/edit/', views.edit_client_profile, name='edit_client_profile'),
]