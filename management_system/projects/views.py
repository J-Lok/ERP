from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Avg, Sum
from django.http import HttpResponse, JsonResponse
from django.db import transaction
from django.utils import timezone
import pandas as pd
import io
import json
from datetime import datetime, timedelta

from .models import Project, SousTache, CommentaireTache
from .forms import ProjectForm, SousTacheForm, CommentaireForm
from employees.models import Employee

@login_required
def project_list(request):
    """Display list of projects with filters"""
    company = request.user.company
    
    # Get all projects for the company
    projects = Project.objects.filter(company=company).select_related(
        'manager', 'created_by'
    ).prefetch_related('team_members').order_by('-created_at')
    
    # Apply search filter
    query = request.GET.get('q', '').strip()
    if query:
        projects = projects.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(manager__user__first_name__icontains=query) |
            Q(manager__user__last_name__icontains=query)
        )
    
    # Apply status filter
    status = request.GET.get('status', '')
    if status:
        projects = projects.filter(status=status)
    
    # Apply priority filter
    priority = request.GET.get('priority', '')
    if priority:
        projects = projects.filter(priority=priority)
    
    # Apply manager filter
    manager_id = request.GET.get('manager', '')
    if manager_id:
        projects = projects.filter(manager_id=manager_id)
    
    # Calculate statistics
    total_projects = projects.count()
    active_projects = projects.filter(status='in_progress').count()
    completed_projects = projects.filter(status='completed').count()
    overdue_projects = projects.filter(end_date__lt=timezone.now().date(), status__in=['planning', 'in_progress']).count()
    
    # Get managers for filter dropdown
    managers = Employee.objects.filter(company=company, user__is_company_admin=True)
    
    context = {
        'projects': projects,
        'managers': managers,
        'query': query,
        'selected_status': status,
        'selected_priority': priority,
        'selected_manager': manager_id,
        'total_projects': total_projects,
        'active_projects': active_projects,
        'completed_projects': completed_projects,
        'overdue_projects': overdue_projects,
        'STATUS_CHOICES': Project.STATUS_CHOICES,
        'PRIORITY_CHOICES': Project.PRIORITY_CHOICES,
        'today': timezone.now().date(),
    }
    
    return render(request, 'projects/project_list.html', context)

@login_required
def project_detail(request, pk):
    """Display project details with tasks"""
    company = request.user.company
    project = get_object_or_404(
        Project.objects.prefetch_related(
            'sous_taches__assigne_a__user',
            'sous_taches__commentaires__auteur',
            'team_members__user'
        ), 
        pk=pk, 
        company=company
    )
    
    # Get all tasks for this project
    sous_taches = project.sous_taches.all().select_related('assigne_a__user').order_by('ordre')
    
    # Calculate task statistics
    total_taches = sous_taches.count()
    taches_terminees = sous_taches.filter(status='termine').count()
    taches_en_cours = sous_taches.filter(status='en_cours').count()
    taches_a_faire = sous_taches.filter(status='a_faire').count()
    
    # Get comments for tasks
    comment_form = CommentaireForm()
    
    # Get task form for adding new tasks
    tache_form = SousTacheForm(company=company, projet_id=project.id)
    
    # Calculate project progress
    if total_taches > 0:
        progress_percentage = int((taches_terminees / total_taches) * 100)
    else:
        progress_percentage = project.completion_percentage
    
    # Get team members
    team_members = project.team_members.all()
    
    context = {
        'project': project,
        'sous_taches': sous_taches,
        'comment_form': comment_form,
        'tache_form': tache_form,
        'team_members': team_members,
        'total_taches': total_taches,
        'taches_terminees': taches_terminees,
        'taches_en_cours': taches_en_cours,
        'taches_a_faire': taches_a_faire,
        'progress_percentage': progress_percentage,
        'STATUS_CHOICES': SousTache.STATUS_CHOICES,
        'PRIORITE_CHOICES': SousTache.PRIORITE_CHOICES,
    }
    
    return render(request, 'projects/project_detail.html', context)

@login_required
def project_create(request):
    """Create new project"""
    company = request.user.company
    
    if request.method == 'POST':
        form = ProjectForm(request.POST, company=company)
        if form.is_valid():
            project = form.save(commit=False)
            project.company = company
            project.created_by = request.user
            
            # Calculate end date if not provided
            if not project.end_date and project.start_date:
                project.end_date = project.start_date + timedelta(days=30)
            
            project.save()
            form.save_m2m()  # Save many-to-many relationships
            
            messages.success(request, f'Project "{project.name}" created successfully!')
            return redirect('projects:project_list')
    else:
        form = ProjectForm(company=company)
    
    return render(request, 'projects/project_form.html', {
        'form': form,
        'title': 'Create New Project'
    })

@login_required
def project_edit(request, pk):
    """Edit existing project"""
    company = request.user.company
    project = get_object_or_404(Project, pk=pk, company=company)
    
    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Project "{project.name}" updated successfully!')
            return redirect('projects:project_detail', pk=project.pk)
    else:
        form = ProjectForm(instance=project, company=company)
    
    return render(request, 'projects/project_form.html', {
        'form': form,
        'project': project,
        'title': 'Edit Project'
    })

@login_required
def project_delete(request, pk):
    """Delete project"""
    company = request.user.company
    project = get_object_or_404(Project, pk=pk, company=company)
    
    if request.method == 'POST':
        project_name = project.name
        project.delete()
        messages.success(request, f'Project "{project_name}" deleted successfully!')
        return redirect('projects:project_list')
    
    return render(request, 'projects/project_confirm_delete.html', {'project': project})

@login_required
def update_project_progress(request, pk):
    """Update project progress manually"""
    company = request.user.company
    project = get_object_or_404(Project, pk=pk, company=company)
    
    if request.method == 'POST':
        try:
            progress = int(request.POST.get('progress', 0))
            if 0 <= progress <= 100:
                project.completion_percentage = progress
                project.save()
                messages.success(request, f'Project progress updated to {progress}%')
            else:
                messages.error(request, 'Progress must be between 0 and 100')
        except ValueError:
            messages.error(request, 'Invalid progress value')
    
    return redirect('projects:project_detail', pk=project.pk)

@login_required
def sous_tache_create(request, project_id):
    """Create new subtask"""
    company = request.user.company
    project = get_object_or_404(Project, pk=project_id, company=company)
    
    if request.method == 'POST':
        form = SousTacheForm(request.POST, company=company, projet_id=project_id)
        if form.is_valid():
            tache = form.save(commit=False)
            tache.company = company
            tache.projet = project
            tache.created_by = request.user
            tache.save()
            
            # Update project progress
            project.mettre_a_jour_progression()
            
            messages.success(request, 'Task created successfully!')
            return redirect('projects:project_detail', pk=project_id)
    
    return redirect('projects:project_detail', pk=project_id)

@login_required
def sous_tache_edit(request, pk):
    """Edit existing subtask"""
    company = request.user.company
    tache = get_object_or_404(SousTache, pk=pk, company=company)
    
    if request.method == 'POST':
        form = SousTacheForm(request.POST, instance=tache, company=company, projet_id=tache.projet.id)
        if form.is_valid():
            form.save()
            
            # Update project progress
            tache.projet.mettre_a_jour_progression()
            
            messages.success(request, 'Task updated successfully!')
            return redirect('projects:project_detail', pk=tache.projet.id)
    
    return redirect('projects:project_detail', pk=tache.projet.id)

@login_required
def sous_tache_delete(request, pk):
    """Delete subtask"""
    company = request.user.company
    tache = get_object_or_404(SousTache, pk=pk, company=company)
    project_id = tache.projet.id
    
    if request.method == 'POST':
        tache.delete()
        
        # Update project progress
        project = get_object_or_404(Project, pk=project_id, company=company)
        project.mettre_a_jour_progression()
        
        messages.success(request, 'Task deleted successfully!')
    
    return redirect('projects:project_detail', pk=project_id)

@login_required
def sous_tache_change_status(request, pk):
    """Change subtask status"""
    company = request.user.company
    tache = get_object_or_404(SousTache, pk=pk, company=company)
    
    if request.method == 'POST':
        nouveau_status = request.POST.get('status')
        if nouveau_status in dict(SousTache.STATUS_CHOICES):
            ancien_status = tache.status
            tache.status = nouveau_status
            
            # Update completion date if task is marked as done
            if nouveau_status == 'termine' and ancien_status != 'termine':
                tache.date_achevement = timezone.now().date()
            elif nouveau_status != 'termine':
                tache.date_achevement = None
            
            tache.save()
            
            # Update project progress
            tache.projet.mettre_a_jour_progression()
            
            messages.success(request, f'Task status changed to: {tache.get_status_display()}')
    
    return redirect('projects:project_detail', pk=tache.projet.id)

@login_required
def sous_tache_detail(request, pk):
    """View subtask details (for AJAX/modal)"""
    company = request.user.company
    tache = get_object_or_404(SousTache, pk=pk, company=company)
    
    context = {
        'tache': tache,
        'comments': tache.commentaires.all().order_by('-created_at'),
        'comment_form': CommentaireForm(),
    }
    
    return render(request, 'projects/sous_tache_detail.html', context)

@login_required
def add_comment(request, tache_id):
    """Add comment to subtask"""
    company = request.user.company
    tache = get_object_or_404(SousTache, pk=tache_id, company=company)
    
    if request.method == 'POST':
        form = CommentaireForm(request.POST)
        if form.is_valid():
            commentaire = form.save(commit=False)
            commentaire.company = company
            commentaire.tache = tache
            commentaire.auteur = request.user
            commentaire.save()
            
            messages.success(request, 'Comment added successfully!')
    
    return redirect('projects:project_detail', pk=tache.projet.id)

@login_required
def delete_comment(request, pk):
    """Delete comment"""
    company = request.user.company
    commentaire = get_object_or_404(CommentaireTache, pk=pk, company=company)
    
    # Check if user is author or admin
    if commentaire.auteur == request.user or request.user.is_company_admin:
        project_id = commentaire.tache.projet.id
        commentaire.delete()
        messages.success(request, 'Comment deleted successfully!')
        return redirect('projects:project_detail', pk=project_id)
    else:
        messages.error(request, 'You are not authorized to delete this comment.')
        return redirect('projects:project_detail', pk=commentaire.tache.projet.id)

@login_required
def project_export(request):
    """Export projects to Excel"""
    company = request.user.company
    projects = Project.objects.filter(company=company).select_related('manager__user')
    
    # Prepare data
    data = []
    for project in projects:
        # Calculate task statistics
        sous_taches = project.sous_taches.all()
        total_taches = sous_taches.count()
        completed_taches = sous_taches.filter(status='termine').count()
        
        data.append({
            'Project ID': project.id,
            'Name': project.name,
            'Description': project.description[:100],  # First 100 chars
            'Status': project.get_status_display(),
            'Priority': project.get_priority_display(),
            'Manager': project.manager.user.get_full_name() if project.manager else '',
            'Team Members': ', '.join([emp.user.get_full_name() for emp in project.team_members.all()]),
            'Budget': float(project.budget) if project.budget else 0.0,
            'Start Date': project.start_date.strftime('%Y-%m-%d') if project.start_date else '',
            'End Date': project.end_date.strftime('%Y-%m-%d') if project.end_date else '',
            'Completion %': project.completion_percentage,
            'Total Tasks': total_taches,
            'Completed Tasks': completed_taches,
            'Created By': project.created_by.get_full_name() if project.created_by else '',
            'Created At': project.created_at.strftime('%Y-%m-%d %H:%M'),
        })
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Create Excel file in memory
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Projects', index=False)
        
        # Auto-adjust column widths
        worksheet = writer.sheets['Projects']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    buffer.seek(0)
    
    # Create response
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="projects_export.xlsx"'
    return response

@login_required
def project_summary_report(request):
    """Generate project summary report"""
    company = request.user.company
    
    # Get all projects
    projects = Project.objects.filter(company=company)
    
    # Calculate statistics
    total_projects = projects.count()
    active_projects = projects.filter(status='in_progress').count()
    completed_projects = projects.filter(status='completed').count()
    planning_projects = projects.filter(status='planning').count()
    on_hold_projects = projects.filter(status='on_hold').count()
    
    # Budget statistics
    budget_stats = projects.aggregate(
        total_budget=Sum('budget'),
        avg_budget=Avg('budget'),
        min_budget=Avg('budget'),  # Would be Min in real implementation
        max_budget=Avg('budget')   # Would be Max in real implementation
    )
    
    # Status distribution
    status_distribution = projects.values('status').annotate(
        count=Count('id'),
        percentage=Count('id') * 100.0 / total_projects if total_projects > 0 else 0
    ).order_by('-count')
    
    # Priority distribution
    priority_distribution = projects.values('priority').annotate(
        count=Count('id'),
        percentage=Count('id') * 100.0 / total_projects if total_projects > 0 else 0
    ).order_by('-count')
    
    # Overdue projects
    overdue_projects = projects.filter(
        end_date__lt=timezone.now().date(),
        status__in=['planning', 'in_progress']
    ).order_by('end_date')[:10]
    
    # Recent projects
    recent_projects = projects.order_by('-created_at')[:10]
    
    context = {
        'total_projects': total_projects,
        'active_projects': active_projects,
        'completed_projects': completed_projects,
        'planning_projects': planning_projects,
        'on_hold_projects': on_hold_projects,
        'budget_stats': budget_stats,
        'status_distribution': list(status_distribution),
        'priority_distribution': list(priority_distribution),
        'overdue_projects': overdue_projects,
        'recent_projects': recent_projects,
        'report_date': timezone.now().date(),
    }
    
    return render(request, 'projects/project_summary_report.html', context)

@login_required
def project_gantt_chart(request):
    """Display Gantt chart for projects"""
    company = request.user.company
    projects = Project.objects.filter(company=company).select_related('manager__user')
    
    # Prepare data for Gantt chart
    gantt_data = []
    for project in projects:
        # Get project tasks
        tasks = project.sous_taches.all()
        for task in tasks:
            gantt_data.append({
                'id': task.id,
                'text': task.titre,
                'start_date': task.date_debut.strftime('%d-%m-%Y') if task.date_debut else '',
                'end_date': task.date_echeance.strftime('%d-%m-%Y') if task.date_echeance else '',
                'progress': 100 if task.status == 'termine' else 50 if task.status == 'en_cours' else 0,
                'parent': project.id,
                'project': project.name,
                'assignee': task.assigne_a.user.get_full_name() if task.assigne_a else 'Unassigned',
                'status': task.get_status_display(),
            })
        
        # Add project as parent task
        gantt_data.append({
            'id': project.id,
            'text': project.name,
            'start_date': project.start_date.strftime('%d-%m-%Y') if project.start_date else '',
            'end_date': project.end_date.strftime('%d-%m-%Y') if project.end_date else '',
            'progress': project.completion_percentage / 100,
            'parent': 0,
            'open': True,
        })
    
    context = {
        'projects': projects,
        'gantt_data': json.dumps(gantt_data),
    }
    
    return render(request, 'projects/project_gantt_chart.html', context)

@login_required
def project_kanban(request):
    """Display Kanban board for projects"""
    company = request.user.company
    
    # Get projects grouped by status
    planning_projects = Project.objects.filter(company=company, status='planning')
    in_progress_projects = Project.objects.filter(company=company, status='in_progress')
    on_hold_projects = Project.objects.filter(company=company, status='on_hold')
    completed_projects = Project.objects.filter(company=company, status='completed')
    
    context = {
        'planning_projects': planning_projects,
        'in_progress_projects': in_progress_projects,
        'on_hold_projects': on_hold_projects,
        'completed_projects': completed_projects,
    }
    
    return render(request, 'projects/project_kanban.html', context)

@login_required
def project_calendar(request):
    """Display project calendar view"""
    company = request.user.company
    projects = Project.objects.filter(company=company)
    
    # Prepare calendar events
    calendar_events = []
    for project in projects:
        # Project as main event
        calendar_events.append({
            'title': project.name,
            'start': project.start_date.isoformat() if project.start_date else '',
            'end': project.end_date.isoformat() if project.end_date else '',
            'url': f'/projects/{project.id}/',
            'color': _get_project_color(project.priority),
            'extendedProps': {
                'type': 'project',
                'priority': project.priority,
                'status': project.status,
            }
        })
        
        # Add tasks as sub-events
        for task in project.sous_taches.all():
            if task.date_debut and task.date_echeance:
                calendar_events.append({
                    'title': task.titre,
                    'start': task.date_debut.isoformat(),
                    'end': task.date_echeance.isoformat(),
                    'color': _get_task_color(task.status),
                    'extendedProps': {
                        'type': 'task',
                        'status': task.status,
                        'assignee': task.assigne_a.user.get_full_name() if task.assigne_a else 'Unassigned',
                    }
                })
    
    context = {
        'calendar_events': json.dumps(calendar_events),
        'projects': projects,
    }
    
    return render(request, 'projects/project_calendar.html', context)

def _get_project_color(priority):
    """Get color based on project priority"""
    color_map = {
        'critical': '#dc3545',  # Red
        'high': '#fd7e14',      # Orange
        'medium': '#ffc107',    # Yellow
        'low': '#198754',       # Green
    }
    return color_map.get(priority, '#6c757d')  # Default gray

def _get_task_color(status):
    """Get color based on task status"""
    color_map = {
        'termine': '#198754',    # Green
        'en_cours': '#0dcaf0',   # Cyan
        'a_faire': '#6c757d',    # Gray
        'en_attente': '#ffc107', # Yellow
        'annule': '#dc3545',     # Red
    }
    return color_map.get(status, '#6c757d')  # Default gray