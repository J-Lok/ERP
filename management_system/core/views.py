"""
core/views.py

Central dashboard view. All queries are scoped to request.user.company
so no data leaks across tenants.
"""

import logging

from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from employees.models import Employee
from inventory.models import Stock
from projects.models import Project

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    """
    Main dashboard — company-scoped statistics and recent activity.

    Redirects to the login page (via @login_required) if the user is not
    authenticated.  If the user has no company yet (edge case during
    on-boarding), they are redirected to company registration.
    """
    company = request.user.company

    if company is None:
        # Unanticipated state — guide the user instead of crashing
        logger.warning('User %s has no company on dashboard access.', request.user.email)
        return redirect('accounts:company_register')

    # ------------------------------------------------------------------
    # Aggregate statistics — single query per model, no N+1
    # ------------------------------------------------------------------
    employee_stats = (
        Employee.objects
        .filter(company=company)
        .aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(status='active')),
        )
    )

    project_stats = (
        Project.objects
        .filter(company=company)
        .aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(status='in_progress')),
            completed=Count('id', filter=Q(status='completed')),
        )
    )

    stock_stats = (
        Stock.objects
        .filter(company=company)
        .aggregate(
            total=Count('id'),
            low=Count('id', filter=Q(quantity__lte=F('reorder_level'))),
        )
    )

    # ------------------------------------------------------------------
    # Recent activity feeds
    # ------------------------------------------------------------------
    recent_projects = (
        Project.objects
        .filter(company=company)
        .order_by('-created_at')
        [:5]
    )

    recent_employees = (
        Employee.objects
        .filter(company=company)
        .select_related('user')
        .order_by('-created_at')
        [:5]
    )

    low_stock_items = (
        Stock.objects
        .filter(company=company, quantity__lte=F('reorder_level'))
        .select_related()
        .order_by('quantity')
        [:10]
    )

    context = {
        'company': company,

        # Employee stats
        'total_employees': employee_stats['total'],
        'active_employees': employee_stats['active'],

        # Project stats
        'total_projects': project_stats['total'],
        'active_projects': project_stats['active'],
        'completed_projects': project_stats['completed'],

        # Inventory stats
        'total_stock_items': stock_stats['total'],
        'low_stock_count': stock_stats['low'],

        # Activity feeds
        'recent_projects': recent_projects,
        'recent_employees': recent_employees,
        'low_stock_items': low_stock_items,

        # Useful in templates for greeting / time-based messages
        'now': timezone.now(),
    }

    return render(request, 'core/dashboard.html', context)