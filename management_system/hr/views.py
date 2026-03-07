from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from accounts.decorators import role_required

from .models import Position, LeaveRequest
from .forms import PositionForm, LeaveRequestForm


# HR dashboard
@role_required(['admin', 'hr_manager'])
def index(request):
    return render(request, 'hr/index.html')


@role_required(['admin', 'hr_manager'])
def position_list(request):
    company = request.user.company
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    positions = Position.objects.filter(company=company).order_by('title')
    paginator = Paginator(positions, 25)
    page = request.GET.get('page')
    try:
        positions_page = paginator.page(page)
    except PageNotAnInteger:
        positions_page = paginator.page(1)
    except EmptyPage:
        positions_page = paginator.page(paginator.num_pages)
    return render(request, 'hr/position_list.html', {'positions': positions_page})


@role_required(['admin', 'hr_manager'])
def position_create(request):
    company = request.user.company
    if request.method == 'POST':
        form = PositionForm(request.POST)
        if form.is_valid():
            pos = form.save(commit=False)
            pos.company = company
            pos.save()
            messages.success(request, 'Position added.')
            return redirect('hr:position_list')
    else:
        form = PositionForm()
    return render(request, 'hr/position_form.html', {'form': form, 'title': 'New Position'})


@role_required(['admin', 'hr_manager'])
def leave_list(request):
    company = request.user.company
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    leaves = LeaveRequest.objects.filter(company=company).select_related('employee').order_by('-requested_at')
    paginator = Paginator(leaves, 25)
    page = request.GET.get('page')
    try:
        leaves_page = paginator.page(page)
    except PageNotAnInteger:
        leaves_page = paginator.page(1)
    except EmptyPage:
        leaves_page = paginator.page(paginator.num_pages)
    return render(request, 'hr/leave_list.html', {'leaves': leaves_page})


@role_required(['admin', 'hr_manager'])
def leave_create(request):
    company = request.user.company
    if request.method == 'POST':
        form = LeaveRequestForm(request.POST)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.company = company
            leave.save()
            messages.success(request, 'Leave request submitted.')
            return redirect('hr:leave_list')
    else:
        form = LeaveRequestForm()
    return render(request, 'hr/leave_form.html', {'form': form, 'title': 'Request Leave'})


@role_required(['admin', 'hr_manager'])
def position_edit(request, pk):
    company = request.user.company
    pos = get_object_or_404(Position, pk=pk, company=company)
    if request.method == 'POST':
        form = PositionForm(request.POST, instance=pos)
        if form.is_valid():
            form.save()
            messages.success(request, 'Position updated.')
            return redirect('hr:position_list')
    else:
        form = PositionForm(instance=pos)
    return render(request, 'hr/position_form.html', {'form': form, 'title': 'Edit Position'})


@role_required(['admin', 'hr_manager'])
def leave_edit(request, pk):
    company = request.user.company
    leave = get_object_or_404(LeaveRequest, pk=pk, company=company)
    if request.method == 'POST':
        form = LeaveRequestForm(request.POST, instance=leave)
        if form.is_valid():
            form.save()
            messages.success(request, 'Leave request updated.')
            return redirect('hr:leave_list')
    else:
        form = LeaveRequestForm(instance=leave)
    return render(request, 'hr/leave_form.html', {'form': form, 'title': 'Edit Leave Request'})


@role_required(['admin', 'hr_manager'])
def position_delete(request, pk):
    company = request.user.company
    pos = get_object_or_404(Position, pk=pk, company=company)
    if request.method == 'POST':
        messages.success(request, f'Position {pos.title} deleted.')
        pos.delete()
        return redirect('hr:position_list')
    return render(request, 'hr/position_confirm_delete.html', {'position': pos})


@role_required(['admin', 'hr_manager'])
def leave_delete(request, pk):
    company = request.user.company
    leave = get_object_or_404(LeaveRequest, pk=pk, company=company)
    if request.method == 'POST':
        messages.success(request, 'Leave request deleted.')
        leave.delete()
        return redirect('hr:leave_list')
    return render(request, 'hr/leave_confirm_delete.html', {'leave': leave})
