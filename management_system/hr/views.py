"""
hr/views.py

HR module views:
  - Dashboard with stats
  - Position management (CRUD), linked to employees
  - Leave request management (CRUD + approve/deny)
  - Employee self-service leave submission
"""

import logging
from datetime import timedelta

from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from employees.models import Employee

from .forms import LeaveRequestForm, PositionForm
from .models import LeaveRequest, Position

HR_ROLES = ['admin', 'hr_manager']
# Employees can submit their own leave requests
LEAVE_SUBMIT_ROLES = ['admin', 'hr_manager', 'manager', 'employee', 'secretary', 'accountant']

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@role_required(*HR_ROLES)
def index(request):
    company = request.user.company
    today = timezone.localdate()

    # Leave stats
    all_leaves = LeaveRequest.objects.filter(company=company)
    pending_count = all_leaves.filter(status='pending').count()
    approved_count = all_leaves.filter(status='approved').count()
    denied_count = all_leaves.filter(status='denied').count()

    # Currently on leave
    on_leave_now = all_leaves.filter(
        status='approved',
        start_date__lte=today,
        end_date__gte=today,
    ).select_related('employee__user').order_by('end_date')

    # Upcoming approved leaves (next 30 days)
    upcoming = all_leaves.filter(
        status='approved',
        start_date__gt=today,
        start_date__lte=today + timedelta(days=30),
    ).select_related('employee__user').order_by('start_date')[:5]

    # Pending requests needing review
    pending_requests = all_leaves.filter(status='pending').select_related(
        'employee__user'
    ).order_by('start_date')[:10]

    # Position stats
    position_count = Position.objects.filter(company=company).count()

    # Leave by type (for summary)
    leave_by_type = (
        all_leaves.filter(status='approved')
        .values('leave_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    context = {
        'pending_count': pending_count,
        'approved_count': approved_count,
        'denied_count': denied_count,
        'on_leave_now': on_leave_now,
        'upcoming': upcoming,
        'pending_requests': pending_requests,
        'position_count': position_count,
        'leave_by_type': leave_by_type,
        'today': today,
    }
    return render(request, 'hr/index.html', context)


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------

@role_required(*HR_ROLES)
def position_list(request):
    company = request.user.company
    positions = (
        Position.objects
        .filter(company=company)
        .annotate(emp_count=Count('employees', filter=Q(employees__status='active')))
        .order_by('salary_grade', 'title')
    )

    query = request.GET.get('q', '').strip()
    if query:
        positions = positions.filter(title__icontains=query)

    paginator = Paginator(positions, 25)
    page = request.GET.get('page')
    try:
        positions_page = paginator.page(page)
    except PageNotAnInteger:
        positions_page = paginator.page(1)
    except EmptyPage:
        positions_page = paginator.page(paginator.num_pages)

    return render(request, 'hr/position_list.html', {
        'positions': positions_page,
        'query': query,
    })


@role_required(*HR_ROLES)
def position_create(request):
    company = request.user.company
    if request.method == 'POST':
        form = PositionForm(request.POST)
        if form.is_valid():
            pos = form.save(commit=False)
            pos.company = company
            pos.save()
            messages.success(request, f'Position "{pos.title}" created.')
            return redirect('hr:position_list')
    else:
        form = PositionForm()
    return render(request, 'hr/position_form.html', {'form': form, 'title': 'New Position'})


@role_required(*HR_ROLES)
def position_edit(request, pk):
    company = request.user.company
    pos = get_object_or_404(Position, pk=pk, company=company)
    if request.method == 'POST':
        form = PositionForm(request.POST, instance=pos)
        if form.is_valid():
            form.save()
            messages.success(request, f'Position "{pos.title}" updated.')
            return redirect('hr:position_list')
    else:
        form = PositionForm(instance=pos)
    return render(request, 'hr/position_form.html', {'form': form, 'title': 'Edit Position'})


@role_required(*HR_ROLES)
def position_delete(request, pk):
    company = request.user.company
    pos = get_object_or_404(Position, pk=pk, company=company)
    if request.method == 'POST':
        title = pos.title
        pos.delete()
        messages.success(request, f'Position "{title}" deleted.')
        return redirect('hr:position_list')
    return render(request, 'hr/position_confirm_delete.html', {'position': pos})


# ---------------------------------------------------------------------------
# Leave Requests — HR management views
# ---------------------------------------------------------------------------

@role_required(*HR_ROLES)
def leave_list(request):
    company = request.user.company
    qs = (
        LeaveRequest.objects
        .filter(company=company)
        .select_related('employee__user', 'reviewed_by')
        .order_by('-requested_at')
    )

    # Filters
    status_filter = request.GET.get('status', '').strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    type_filter = request.GET.get('leave_type', '').strip()
    if type_filter:
        qs = qs.filter(leave_type=type_filter)

    query = request.GET.get('q', '').strip()
    if query:
        qs = qs.filter(
            Q(employee__user__first_name__icontains=query) |
            Q(employee__user__last_name__icontains=query) |
            Q(employee__employee_id__icontains=query)
        )

    paginator = Paginator(qs, 25)
    page = request.GET.get('page')
    try:
        leaves_page = paginator.page(page)
    except PageNotAnInteger:
        leaves_page = paginator.page(1)
    except EmptyPage:
        leaves_page = paginator.page(paginator.num_pages)

    return render(request, 'hr/leave_list.html', {
        'leaves': leaves_page,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'query': query,
        'status_choices': LeaveRequest.STATUS_CHOICES,
        'leave_types': LeaveRequest.LEAVE_TYPES,
        'today': timezone.localdate(),
    })


@role_required(*HR_ROLES)
def leave_create(request):
    company = request.user.company
    if request.method == 'POST':
        form = LeaveRequestForm(request.POST, company=company)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.company = company
            leave.submitted_by = request.user
            leave.full_clean()
            leave.save()
            messages.success(request, 'Leave request submitted.')
            return redirect('hr:leave_list')
    else:
        form = LeaveRequestForm(company=company)
    return render(request, 'hr/leave_form.html', {'form': form, 'title': 'New Leave Request'})


@role_required(*HR_ROLES)
def leave_edit(request, pk):
    company = request.user.company
    leave = get_object_or_404(LeaveRequest, pk=pk, company=company)
    if request.method == 'POST':
        form = LeaveRequestForm(request.POST, instance=leave, company=company)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.full_clean()
            leave.save()
            messages.success(request, 'Leave request updated.')
            return redirect('hr:leave_list')
    else:
        form = LeaveRequestForm(instance=leave, company=company)
    return render(request, 'hr/leave_form.html', {'form': form, 'title': 'Edit Leave Request'})


@role_required(*HR_ROLES)
def leave_delete(request, pk):
    company = request.user.company
    leave = get_object_or_404(LeaveRequest, pk=pk, company=company)
    if request.method == 'POST':
        leave.delete()
        messages.success(request, 'Leave request deleted.')
        return redirect('hr:leave_list')
    return render(request, 'hr/leave_confirm_delete.html', {'leave': leave})


@role_required(*HR_ROLES)
@require_POST
def leave_approve(request, pk):
    company = request.user.company
    leave = get_object_or_404(LeaveRequest, pk=pk, company=company)
    if leave.status != 'pending':
        messages.warning(request, 'Only pending requests can be approved.')
    else:
        leave.approve(reviewed_by=request.user)
        messages.success(
            request,
            f'{leave.employee.full_name}\'s {leave.get_leave_type_display()} approved.'
        )
    return redirect('hr:leave_list')


@role_required(*HR_ROLES)
@require_POST
def leave_deny(request, pk):
    company = request.user.company
    leave = get_object_or_404(LeaveRequest, pk=pk, company=company)
    if leave.status not in ('pending', 'approved'):
        messages.warning(request, 'This request cannot be denied.')
    else:
        leave.deny(reviewed_by=request.user)
        messages.success(
            request,
            f'{leave.employee.full_name}\'s {leave.get_leave_type_display()} denied.'
        )
    return redirect('hr:leave_list')


# ---------------------------------------------------------------------------
# Employee self-service
# ---------------------------------------------------------------------------

@role_required(*LEAVE_SUBMIT_ROLES)
def my_leave_list(request):
    """Employee view: see own leave requests."""
    user = request.user
    try:
        employee = user.employee_profile
    except Exception:
        messages.error(request, 'No employee profile found for your account.')
        return redirect('core:dashboard')

    leaves = (
        LeaveRequest.objects
        .filter(employee=employee)
        .order_by('-requested_at')
    )
    return render(request, 'hr/my_leave_list.html', {
        'leaves': leaves,
        'today': timezone.localdate(),
    })


@role_required(*LEAVE_SUBMIT_ROLES)
def my_leave_create(request):
    """Employee self-service: submit own leave request."""
    user = request.user
    try:
        employee = user.employee_profile
    except Exception:
        messages.error(request, 'No employee profile found for your account.')
        return redirect('core:dashboard')

    company = user.company
    if request.method == 'POST':
        form = LeaveRequestForm(request.POST, company=company, self_employee=employee)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.company = company
            leave.employee = employee
            leave.submitted_by = user
            try:
                leave.full_clean()
            except Exception as e:
                messages.error(request, str(e))
                return render(request, 'hr/my_leave_form.html', {'form': form})
            leave.save()
            messages.success(request, 'Leave request submitted. Awaiting HR approval.')
            return redirect('hr:my_leave_list')
    else:
        form = LeaveRequestForm(company=company, self_employee=employee)
    return render(request, 'hr/my_leave_form.html', {'form': form})