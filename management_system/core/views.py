from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q, F, Count
from employees.models import Employee
from projects.models import Project
from inventory.models import Stock

@login_required
def dashboard(request):
    """Dashboard with company-specific data"""
    company = request.user.company
    
    # Company statistics
    total_employees = Employee.objects.filter(company=company, status='active').count()
    total_projects = Project.objects.filter(company=company).count()
    active_projects = Project.objects.filter(company=company, status='in_progress').count()
    total_stock_items = Stock.objects.filter(company=company).count()
    low_stock_items = Stock.objects.filter(company=company, quantity__lte=F('reorder_level')).count()
    
    # Recent data
    recent_projects = Project.objects.filter(company=company).order_by('-created_at')[:5]
    recent_employees = Employee.objects.filter(company=company).select_related('user').order_by('-created_at')[:5]
    
    context = {
        'company': company,
        'total_employees': total_employees,
        'total_projects': total_projects,
        'active_projects': active_projects,
        'total_stock_items': total_stock_items,
        'low_stock_items': low_stock_items,
        'recent_projects': recent_projects,
        'recent_employees': recent_employees,
    }
    
    return render(request, 'core/dashboard.html', context)