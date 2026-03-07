from django.urls import path
from . import views

app_name = 'hr'

urlpatterns = [
    path('', views.index, name='index'),
    path('positions/', views.position_list, name='position_list'),
    path('positions/new/', views.position_create, name='position_create'),
    path('positions/<int:pk>/edit/', views.position_edit, name='position_edit'),
    path('positions/<int:pk>/delete/', views.position_delete, name='position_delete'),
    path('leaves/', views.leave_list, name='leave_list'),
    path('leaves/new/', views.leave_create, name='leave_create'),
    path('leaves/<int:pk>/edit/', views.leave_edit, name='leave_edit'),
    path('leaves/<int:pk>/delete/', views.leave_delete, name='leave_delete'),
]
