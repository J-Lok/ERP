from django.urls import path
from . import views

app_name = 'hr'

urlpatterns = [
    # Dashboard
    path('', views.index, name='index'),

    # Positions
    path('positions/', views.position_list, name='position_list'),
    path('positions/new/', views.position_create, name='position_create'),
    path('positions/<int:pk>/edit/', views.position_edit, name='position_edit'),
    path('positions/<int:pk>/delete/', views.position_delete, name='position_delete'),

    # Leave requests — HR management
    path('leaves/', views.leave_list, name='leave_list'),
    path('leaves/new/', views.leave_create, name='leave_create'),
    path('leaves/<int:pk>/edit/', views.leave_edit, name='leave_edit'),
    path('leaves/<int:pk>/delete/', views.leave_delete, name='leave_delete'),
    path('leaves/<int:pk>/approve/', views.leave_approve, name='leave_approve'),
    path('leaves/<int:pk>/deny/', views.leave_deny, name='leave_deny'),

    # Employee self-service
    path('my-leaves/', views.my_leave_list, name='my_leave_list'),
    path('my-leaves/new/', views.my_leave_create, name='my_leave_create'),
]