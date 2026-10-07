from django.urls import path

from . import views

app_name = 'suppliers'

urlpatterns = [
    path('', views.supplier_list, name='supplier_list'),
    path('create/', views.supplier_create, name='supplier_create'),
    path('quick-create/', views.supplier_quick_create, name='supplier_quick_create'),
    path('<int:pk>/', views.supplier_detail, name='supplier_detail'),
    path('<int:pk>/edit/', views.supplier_edit, name='supplier_edit'),
    path('<int:pk>/delete/', views.supplier_delete, name='supplier_delete'),
]
