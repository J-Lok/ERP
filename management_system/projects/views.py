"""
projects/views.py
"""

import io
import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import Avg, Count, Max, Min, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from employees.models import Employee
from .forms import CommentaireForm, ProjectForm, SousTacheForm
from .models import CommentaireTache, Project, SousTache

logger = logging.getLogger(__name__)
PAGE_SIZE = 20


def _paginate(qs, page_number, per_page=PAGE_SIZE):
    paginator = Paginator(qs, per_page)
    try:
        return paginator.page(page_number)
    except PageNotAnInteger:
        return paginator.page(1)
    except EmptyPage:
        return paginator.page(paginator.num_pages)


# ---------------------------------------------------------------------------
# Project list
# ---------------------------------------------------------------------------

@login_required
def project_list(request):
    company = request.user.company
    today = timezone.localdate()

    projects = (
        Project.objects
        .filter(company=company)
        .select_related('manager__user', 'created_by')
        .prefetch_related('team_members')
        .order_by('-created_at')
    )

    # Filters
    query = request.GET.get('q', '').strip()
    if query:
        projects = projects.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(manager__user__first_name__icontains=query)
            | Q(manager__user__last_name__icontains=query)
        )

    status = request.GET.get('status', '')
    if status in dict(Project.STATUS_CHOICES):
        projects = projects.filter(status=status)

    priority = request.GET.get('priority', '')
    if priority in dict(Project.PRIORITY_CHOICES):
        projects = projects.filter(priority=priority)

    manager_id = request.GET.get('manager', '')
    if manager_id:
        projects = projects.filter(manager_id=manager_id)

    # Stats on unfiltered company queryset so counts are always accurate
    all_projects = Project.objects.filter(company=company)
    stats = all_projects.aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(status='in_progress')),
        completed=Count('id', filter=Q(status='completed')),
        overdue=Count('id', filter=Q(
            end_date__lt=today, status__in=['planning', 'in_progress']
        )),
    )

    managers = Employee.objects.filter(company=company, status='active').select_related('user')

    return render(request, 'projects/project_list.html', {
        'projects': _paginate(projects, request.GET.get('page')),
        'managers': managers,
        'query': query,
        'selected_status': status,
        'selected_priority': priority,
        'selected_manager': manager_id,
        'stats': stats,
        'STATUS_CHOICES': Project.STATUS_CHOICES,
        'PRIORITY_CHOICES': Project.PRIORITY_CHOICES,
        'today': today,
    })


# ---------------------------------------------------------------------------
# Project detail
# ---------------------------------------------------------------------------

@login_required
def project_detail(request, pk):
    company = request.user.company
    project = get_object_or_404(
        Project.objects.prefetch_related(
            'sous_taches__assigne_a__user',
            'sous_taches__commentaires__auteur',
            'team_members__user',
        ),
        pk=pk,
        company=company,
    )

    sous_taches = project.sous_taches.select_related('assigne_a__user').order_by('ordre')

    # Single aggregate instead of 4 separate COUNT queries
    task_stats = sous_taches.aggregate(
        total=Count('id'),
        terminees=Count('id', filter=Q(status='termine')),
        en_cours=Count('id', filter=Q(status='en_cours')),
        a_faire=Count('id', filter=Q(status='a_faire')),
    )

    return render(request, 'projects/project_detail.html', {
        'project': project,
        'sous_taches': sous_taches,
        'task_stats': task_stats,
        'comment_form': CommentaireForm(),
        'tache_form': SousTacheForm(company=company, projet_id=project.id),
        'team_members': project.team_members.all(),
        'progress_percentage': project.completion_percentage,
        'STATUS_CHOICES': SousTache.STATUS_CHOICES,
        'PRIORITE_CHOICES': SousTache.PRIORITE_CHOICES,
    })


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(['GET', 'POST'])
def project_create(request):
    company = request.user.company

    if request.method == 'POST':
        form = ProjectForm(request.POST, company=company)
        if form.is_valid():
            with transaction.atomic():
                project = form.save(commit=False)
                project.company = company
                project.created_by = request.user
                project.save()
                form.save_m2m()

                # Inline subtasks submitted with the creation form
                for title in request.POST.getlist('subtask_titles'):
                    title = title.strip()
                    if title:
                        SousTache.objects.create(
                            company=company,
                            projet=project,
                            titre=title,
                            created_by=request.user,
                        )

                project.update_completion_from_subtasks()

            messages.success(request, f'Project "{project.name}" created.')
            return redirect('projects:project_list')
    else:
        form = ProjectForm(company=company)

    return render(request, 'projects/project_form.html', {'form': form, 'title': 'Create Project'})


@login_required
@require_http_methods(['GET', 'POST'])
def project_edit(request, pk):
    company = request.user.company
    project = get_object_or_404(Project, pk=pk, company=company)

    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project, company=company)
        if form.is_valid():
            with transaction.atomic():
                form.save()
                for title in request.POST.getlist('subtask_titles'):
                    title = title.strip()
                    if title and not project.sous_taches.filter(titre=title).exists():
                        SousTache.objects.create(
                            company=company,
                            projet=project,
                            titre=title,
                            created_by=request.user,
                        )
                project.update_completion_from_subtasks()

            messages.success(request, f'Project "{project.name}" updated.')
            return redirect('projects:project_detail', pk=project.pk)
    else:
        form = ProjectForm(instance=project, company=company)

    return render(request, 'projects/project_form.html', {
        'form': form, 'project': project, 'title': 'Edit Project',
    })


@login_required
@require_http_methods(['GET', 'POST'])
def project_delete(request, pk):
    company = request.user.company
    project = get_object_or_404(Project, pk=pk, company=company)

    if request.method == 'POST':
        name = project.name
        project.delete()
        messages.success(request, f'Project "{name}" deleted.')
        return redirect('projects:project_list')

    return render(request, 'projects/project_confirm_delete.html', {'project': project})


@login_required
@require_http_methods(['POST'])
def update_project_progress(request, pk):
    """Manually override project completion percentage."""
    company = request.user.company
    project = get_object_or_404(Project, pk=pk, company=company)

    try:
        progress = int(request.POST.get('progress', 0))
    except (ValueError, TypeError):
        messages.error(request, 'Invalid progress value.')
        return redirect('projects:project_detail', pk=pk)

    if 0 <= progress <= 100:
        project.completion_percentage = progress
        project.save(update_fields=['completion_percentage', 'updated_at'])
        messages.success(request, f'Progress updated to {progress}%.')
    else:
        messages.error(request, 'Progress must be between 0 and 100.')

    return redirect('projects:project_detail', pk=pk)


# ---------------------------------------------------------------------------
# Sub-tasks
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(['POST'])
def sous_tache_create(request, project_id):
    company = request.user.company
    project = get_object_or_404(Project, pk=project_id, company=company)

    form = SousTacheForm(request.POST, company=company, projet_id=project_id)
    if form.is_valid():
        tache = form.save(commit=False)
        tache.company = company
        tache.projet = project
        tache.created_by = request.user
        tache.save()
        project.update_completion_from_subtasks()
        messages.success(request, 'Task created.')
    else:
        messages.error(request, 'Could not create task. Please check the form.')

    return redirect('projects:project_detail', pk=project_id)


@login_required
@require_http_methods(['POST'])
def sous_tache_edit(request, pk):
    company = request.user.company
    tache = get_object_or_404(SousTache, pk=pk, company=company)

    form = SousTacheForm(
        request.POST, instance=tache, company=company, projet_id=tache.projet_id
    )
    if form.is_valid():
        form.save()
        tache.projet.update_completion_from_subtasks()
        messages.success(request, 'Task updated.')
    else:
        messages.error(request, 'Could not update task.')

    return redirect('projects:project_detail', pk=tache.projet_id)


@login_required
@require_http_methods(['POST'])
def sous_tache_delete(request, pk):
    company = request.user.company
    tache = get_object_or_404(SousTache, pk=pk, company=company)
    project = tache.projet
    tache.delete()
    project.update_completion_from_subtasks()
    messages.success(request, 'Task deleted.')
    return redirect('projects:project_detail', pk=project.pk)


@login_required
@require_http_methods(['POST'])
def sous_tache_change_status(request, pk):
    """Change task status — delegates to SousTache.change_status()."""
    company = request.user.company
    tache = get_object_or_404(SousTache, pk=pk, company=company)
    new_status = request.POST.get('status', '').strip()

    try:
        tache.change_status(new_status)
        messages.success(request, f'Status changed to {tache.get_status_display()}.')
    except Exception as exc:
        messages.error(request, str(exc))

    return redirect('projects:project_detail', pk=tache.projet_id)


@login_required
@require_http_methods(['POST'])
def toggle_subtask_completion(request, pk):
    """
    AJAX endpoint: toggle a task between 'termine' and 'a_faire'.
    Delegates to SousTache.change_status() so all side-effects (date,
    completion_percentage, project rollup) are handled consistently.
    """
    company = request.user.company
    tache = get_object_or_404(SousTache, pk=pk, company=company)

    checked = request.POST.get('checked') == 'true'
    new_status = 'termine' if checked else 'a_faire'
    tache.change_status(new_status)

    # Re-fetch the project's updated completion percentage
    tache.projet.refresh_from_db(fields=['completion_percentage'])
    return JsonResponse({'project_completion': tache.projet.completion_percentage})


@login_required
def sous_tache_detail(request, pk):
    company = request.user.company
    tache = get_object_or_404(SousTache, pk=pk, company=company)
    return render(request, 'projects/sous_tache_detail.html', {
        'tache': tache,
        'comments': tache.commentaires.select_related('auteur').order_by('-created_at'),
        'comment_form': CommentaireForm(),
    })


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(['POST'])
def add_comment(request, tache_id):
    company = request.user.company
    tache = get_object_or_404(SousTache, pk=tache_id, company=company)

    form = CommentaireForm(request.POST)
    if form.is_valid():
        commentaire = form.save(commit=False)
        commentaire.company = company
        commentaire.tache = tache
        commentaire.auteur = request.user
        commentaire.save()
        messages.success(request, 'Comment added.')
    else:
        messages.error(request, 'Comment cannot be empty.')

    return redirect('projects:project_detail', pk=tache.projet_id)


@login_required
@require_http_methods(['POST'])
def delete_comment(request, pk):
    company = request.user.company
    commentaire = get_object_or_404(CommentaireTache, pk=pk, company=company)

    if commentaire.auteur == request.user or request.user.is_company_admin:
        project_id = commentaire.tache.projet_id
        commentaire.delete()
        messages.success(request, 'Comment deleted.')
    else:
        messages.error(request, 'You are not authorised to delete this comment.')
        project_id = commentaire.tache.projet_id

    return redirect('projects:project_detail', pk=project_id)


# ---------------------------------------------------------------------------
# Reports & visualisations
# ---------------------------------------------------------------------------

@login_required
def project_summary_report(request):
    company = request.user.company
    projects = Project.objects.filter(company=company)
    today = timezone.localdate()

    counts = projects.aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(status='in_progress')),
        completed=Count('id', filter=Q(status='completed')),
        planning=Count('id', filter=Q(status='planning')),
        on_hold=Count('id', filter=Q(status='on_hold')),
    )

    budget_stats = projects.aggregate(
        total_budget=Sum('budget'),
        avg_budget=Avg('budget'),
        min_budget=Min('budget'),
        max_budget=Max('budget'),
    )

    total = counts['total'] or 1  # avoid division by zero in annotation
    status_distribution = list(
        projects.values('status')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    priority_distribution = list(
        projects.values('priority')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    overdue_projects = (
        projects.filter(end_date__lt=today, status__in=['planning', 'in_progress'])
        .select_related('manager__user')
        .order_by('end_date')[:10]
    )
    recent_projects = projects.order_by('-created_at')[:10]

    return render(request, 'projects/project_summary_report.html', {
        'counts': counts,
        'budget_stats': budget_stats,
        'status_distribution': status_distribution,
        'priority_distribution': priority_distribution,
        'overdue_projects': overdue_projects,
        'recent_projects': recent_projects,
        'report_date': today,
    })


@login_required
def project_gantt_chart(request):
    company = request.user.company
    projects = (
        Project.objects
        .filter(company=company)
        .select_related('manager__user')
        .prefetch_related('sous_taches__assigne_a__user')
    )

    gantt_data = []
    for project in projects:
        # Parent row
        gantt_data.append({
            'id': project.id,
            'text': project.name,
            'start_date': project.start_date.strftime('%d-%m-%Y'),
            'end_date': project.end_date.strftime('%d-%m-%Y'),
            'progress': round(project.completion_percentage / 100, 2),
            'parent': 0,
            'open': True,
        })
        # Task rows
        for task in project.sous_taches.all():
            gantt_data.append({
                'id': f'task_{task.id}',
                'text': task.titre,
                'start_date': task.date_debut.strftime('%d-%m-%Y') if task.date_debut else '',
                'end_date': task.date_echeance.strftime('%d-%m-%Y') if task.date_echeance else '',
                'progress': (
                    1.0 if task.status == 'termine'
                    else 0.5 if task.status == 'en_cours'
                    else 0.0
                ),
                'parent': project.id,
                'project': project.name,
                'assignee': (
                    task.assigne_a.user.get_full_name()
                    if task.assigne_a else 'Unassigned'
                ),
                'status': task.get_status_display(),
            })

    return render(request, 'projects/project_gantt_chart.html', {
        'projects': projects,
        'gantt_data': json.dumps(gantt_data),
    })


@login_required
def project_kanban(request):
    company = request.user.company
    base_qs = Project.objects.filter(company=company).select_related('manager__user')

    # One query per column — acceptable for typical project counts
    columns = {status: base_qs.filter(status=status) for status, _ in Project.STATUS_CHOICES}

    return render(request, 'projects/project_kanban.html', {
        'columns': columns,
        'STATUS_CHOICES': Project.STATUS_CHOICES,
    })


@login_required
def project_calendar(request):
    company = request.user.company
    projects = (
        Project.objects
        .filter(company=company)
        .prefetch_related('sous_taches__assigne_a__user')
    )

    events = []
    for project in projects:
        events.append({
            'title': project.name,
            'start': project.start_date.isoformat(),
            'end': project.end_date.isoformat(),
            'url': f'/projects/{project.id}/',
            'color': _priority_color(project.priority),
            'extendedProps': {
                'type': 'project',
                'priority': project.priority,
                'status': project.status,
            },
        })
        for task in project.sous_taches.all():
            if task.date_debut and task.date_echeance:
                events.append({
                    'title': task.titre,
                    'start': task.date_debut.isoformat(),
                    'end': task.date_echeance.isoformat(),
                    'color': _status_color(task.status),
                    'extendedProps': {
                        'type': 'task',
                        'status': task.status,
                        'assignee': (
                            task.assigne_a.user.get_full_name()
                            if task.assigne_a else 'Unassigned'
                        ),
                    },
                })

    return render(request, 'projects/project_calendar.html', {
        'calendar_events': json.dumps(events),
        'projects': projects,
    })


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@login_required
def project_export(request):
    """Export all company projects to Excel."""
    import pandas as pd

    company = request.user.company
    projects = (
        Project.objects
        .filter(company=company)
        .select_related('manager__user', 'created_by')
        .prefetch_related('team_members__user', 'sous_taches')
    )

    rows = []
    for project in projects:
        task_stats = project.sous_taches.aggregate(
            total=Count('id'),
            completed=Count('id', filter=Q(status='termine')),
        )
        rows.append({
            'Project ID': project.id,
            'Name': project.name,
            'Description': project.description[:100],
            'Status': project.get_status_display(),
            'Priority': project.get_priority_display(),
            'Manager': project.manager.user.get_full_name() if project.manager else '',
            'Team Members': ', '.join(
                emp.user.get_full_name() for emp in project.team_members.all()
            ),
            'Budget': float(project.budget or 0),
            'Start Date': project.start_date.strftime('%Y-%m-%d'),
            'End Date': project.end_date.strftime('%Y-%m-%d'),
            'Completion %': project.completion_percentage,
            'Total Tasks': task_stats['total'],
            'Completed Tasks': task_stats['completed'],
            'Created By': project.created_by.get_full_name() if project.created_by else '',
            'Created At': project.created_at.strftime('%Y-%m-%d %H:%M'),
        })

    df = pd.DataFrame(rows)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Projects', index=False)
        ws = writer.sheets['Projects']
        for col in ws.columns:
            letter = col[0].column_letter
            width = min(max((len(str(c.value or '')) for c in col), default=10) + 2, 50)
            ws.column_dimensions[letter].width = width

    buffer.seek(0)
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="projects_export.xlsx"'
    return response


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

_PRIORITY_COLORS = {
    'critical': '#dc3545',
    'high': '#fd7e14',
    'medium': '#ffc107',
    'low': '#198754',
}

_STATUS_COLORS = {
    'termine': '#198754',
    'en_cours': '#0dcaf0',
    'a_faire': '#6c757d',
    'en_attente': '#ffc107',
    'annule': '#dc3545',
}


def _priority_color(priority: str) -> str:
    return _PRIORITY_COLORS.get(priority, '#6c757d')


def _status_color(status: str) -> str:
    return _STATUS_COLORS.get(status, '#6c757d')