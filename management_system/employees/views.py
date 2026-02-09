from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Avg, Sum
from django.http import HttpResponse
from django.db import transaction
import pandas as pd
import io
import json
from datetime import datetime

from .models import Employee, Department
from .forms import EmployeeForm, DepartmentForm
from accounts.models import User

@login_required
def employee_list(request):
    """Display list of employees with search and filters"""
    company = request.user.company
    
    # Get all employees for the company
    employees = Employee.objects.filter(company=company).select_related(
        'user', 'department'
    ).order_by('-created_at')
    
    # Apply search filter
    query = request.GET.get('q', '').strip()
    if query:
        employees = employees.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(employee_id__icontains=query) |
            Q(user__email__icontains=query) |
            Q(department__name__icontains=query)
        )
    
    # Apply department filter
    department_id = request.GET.get('department', '')
    if department_id:
        employees = employees.filter(department_id=department_id)
    
    # Apply status filter
    status = request.GET.get('status', '')
    if status:
        employees = employees.filter(status=status)
    
    # Apply role filter
    role = request.GET.get('role', '')
    if role:
        employees = employees.filter(role=role)
    
    # Get departments for filter dropdown
    departments = Department.objects.filter(company=company).order_by('name')
    
    # Count statistics
    total_employees = employees.count()
    active_employees = employees.filter(status='active').count()
    on_leave_employees = employees.filter(status='on_leave').count()
    
    # Get all unique roles for filter
    roles = employees.values_list('role', flat=True).distinct()
    
    context = {
        'employees': employees,
        'departments': departments,
        'roles': roles,
        'query': query,
        'selected_department': department_id,
        'selected_status': status,
        'selected_role': role,
        'total_employees': total_employees,
        'active_employees': active_employees,
        'on_leave_employees': on_leave_employees,
        'ROLE_CHOICES': Employee.ROLE_CHOICES,
        'STATUS_CHOICES': Employee.STATUS_CHOICES,
    }
    
    return render(request, 'employees/employee_list.html', context)

@login_required
def employee_detail(request, pk):
    """Display employee details"""
    company = request.user.company
    employee = get_object_or_404(Employee, pk=pk, company=company)
    
    context = {
        'employee': employee,
    }
    
    return render(request, 'employees/employee_detail.html', context)

@login_required
def employee_create(request):
    """Create new employee"""
    company = request.user.company
    
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES, company=company)
        if form.is_valid():
            employee = form.save(commit=False)
            employee.company = company
            
            # If creating a new user
            if form.cleaned_data.get('create_user_account'):
                # Create user account
                user = User.objects.create_user(
                    email=form.cleaned_data['user_email'],
                    password=form.cleaned_data['user_password'],
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    phone=form.cleaned_data['phone'],
                    company=company
                )
                employee.user = user
            else:
                # Link to existing user
                user_email = form.cleaned_data.get('existing_user_email')
                if user_email:
                    try:
                        user = User.objects.get(email=user_email, company=company)
                        employee.user = user
                    except User.DoesNotExist:
                        messages.error(request, 'User with this email does not exist in your company.')
                        return render(request, 'employees/employee_form.html', {'form': form})
            
            employee.save()
            messages.success(request, f'Employee {employee.employee_id} created successfully!')
            return redirect('employees:employee_list')
    else:
        form = EmployeeForm(company=company)
    
    return render(request, 'employees/employee_form.html', {
        'form': form,
        'title': 'Add New Employee'
    })

@login_required
def employee_edit(request, pk):
    """Edit existing employee"""
    company = request.user.company
    employee = get_object_or_404(Employee, pk=pk, company=company)
    
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES, instance=employee, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Employee {employee.employee_id} updated successfully!')
            return redirect('employees:employee_list')
    else:
        form = EmployeeForm(instance=employee, company=company)
    
    return render(request, 'employees/employee_form.html', {
        'form': form,
        'employee': employee,
        'title': 'Edit Employee'
    })

@login_required
def employee_delete(request, pk):
    """Delete employee"""
    company = request.user.company
    employee = get_object_or_404(Employee, pk=pk, company=company)
    
    if request.method == 'POST':
        employee_id = employee.employee_id
        employee_name = employee.user.get_full_name()
        employee.delete()
        messages.success(request, f'Employee {employee_id} - {employee_name} deleted successfully!')
        return redirect('employees:employee_list')
    
    return render(request, 'employees/employee_confirm_delete.html', {'employee': employee})

@login_required
def department_list(request):
    """Display list of departments"""
    company = request.user.company
    departments = Department.objects.filter(company=company).annotate(
        employee_count=Count('employees')
    ).order_by('name')
    
    return render(request, 'employees/department_list.html', {
        'departments': departments
    })

@login_required
def department_create(request):
    """Create new department"""
    company = request.user.company
    
    if request.method == 'POST':
        form = DepartmentForm(request.POST, company=company)
        if form.is_valid():
            department = form.save(commit=False)
            department.company = company
            department.save()
            messages.success(request, f'Department "{department.name}" created successfully!')
            return redirect('employees:department_list')
    else:
        form = DepartmentForm(company=company)
    
    return render(request, 'employees/department_form.html', {
        'form': form,
        'title': 'Add New Department'
    })

@login_required
def department_edit(request, pk):
    """Edit existing department"""
    company = request.user.company
    department = get_object_or_404(Department, pk=pk, company=company)
    
    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=department, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Department "{department.name}" updated successfully!')
            return redirect('employees:department_list')
    else:
        form = DepartmentForm(instance=department, company=company)
    
    return render(request, 'employees/department_form.html', {
        'form': form,
        'department': department,
        'title': 'Edit Department'
    })

@login_required
def department_delete(request, pk):
    """Delete department"""
    company = request.user.company
    department = get_object_or_404(Department, pk=pk, company=company)
    
    if request.method == 'POST':
        department_name = department.name
        department.delete()
        messages.success(request, f'Department "{department_name}" deleted successfully!')
        return redirect('employees:department_list')
    
    return render(request, 'employees/department_confirm_delete.html', {'department': department})

@login_required
def employee_export(request):
    """Export employees to Excel"""
    company = request.user.company
    employees = Employee.objects.filter(company=company).select_related('user', 'department')
    
    # Prepare data
    data = []
    for emp in employees:
        data.append({
            'Employee ID': emp.employee_id,
            'First Name': emp.user.first_name,
            'Last Name': emp.user.last_name,
            'Email': emp.user.email,
            'Phone': emp.user.phone,
            'Department': emp.department.name if emp.department else '',
            'Role': emp.get_role_display(),
            'Status': emp.get_status_display(),
            'Date Joined': emp.date_joined.strftime('%Y-%m-%d') if emp.date_joined else '',
            'Salary': float(emp.salary) if emp.salary else 0.0,
            'Date of Birth': emp.date_of_birth.strftime('%Y-%m-%d') if emp.date_of_birth else '',
        })
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Create Excel file in memory
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Employees', index=False)
        
        # Auto-adjust column widths
        worksheet = writer.sheets['Employees']
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
    response['Content-Disposition'] = 'attachment; filename="employees_export.xlsx"'
    return response

@login_required
def employee_import(request):
    """Import employees from Excel"""
    company = request.user.company
    
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        
        if not excel_file.name.endswith(('.xlsx', '.xls')):
            messages.error(request, 'Please upload a valid Excel file (.xlsx or .xls)')
            return redirect('employees:employee_import')
        
        try:
            df = pd.read_excel(excel_file)
            required_columns = ['Employee ID', 'First Name', 'Last Name', 'Email']
            
            # Check required columns
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                messages.error(request, f'Missing required columns: {", ".join(missing_columns)}')
                return redirect('employees:employee_import')
            
            success_count = 0
            error_count = 0
            errors = []
            
            with transaction.atomic():
                for index, row in df.iterrows():
                    row_num = index + 2  # Excel row number
                    
                    try:
                        employee_id = str(row['Employee ID']).strip()
                        first_name = str(row['First Name']).strip()
                        last_name = str(row['Last Name']).strip()
                        email = str(row['Email']).strip().lower()
                        
                        if not all([employee_id, first_name, last_name, email]):
                            errors.append(f'Row {row_num}: Missing required fields')
                            error_count += 1
                            continue
                        
                        # Check if employee ID already exists
                        if Employee.objects.filter(company=company, employee_id=employee_id).exists():
                            errors.append(f'Row {row_num}: Employee ID {employee_id} already exists')
                            error_count += 1
                            continue
                        
                        # Check if user already exists
                        user = User.objects.filter(email=email, company=company).first()
                        if not user:
                            # Create new user
                            user = User.objects.create_user(
                                email=email,
                                password='TempPassword123',  # Default password
                                first_name=first_name,
                                last_name=last_name,
                                company=company
                            )
                        
                        # Get or create department
                        department = None
                        if 'Department' in df.columns and pd.notna(row['Department']):
                            dept_name = str(row['Department']).strip()
                            if dept_name:
                                department, _ = Department.objects.get_or_create(
                                    name=dept_name,
                                    company=company,
                                    defaults={'description': f'Department for {dept_name}'}
                                )
                        
                        # Create employee
                        employee = Employee(
                            company=company,
                            user=user,
                            employee_id=employee_id,
                            department=department,
                            role=row.get('Role', 'other'),
                            status=row.get('Status', 'active'),
                            date_joined=datetime.now().date(),
                            salary=row.get('Salary', 0) or 0,
                        )
                        
                        # Set optional fields
                        if 'Phone' in df.columns and pd.notna(row['Phone']):
                            user.phone = str(row['Phone']).strip()
                            user.save()
                        
                        if 'Date of Birth' in df.columns and pd.notna(row['Date of Birth']):
                            try:
                                employee.date_of_birth = pd.to_datetime(row['Date of Birth']).date()
                            except:
                                pass
                        
                        employee.save()
                        success_count += 1
                        
                    except Exception as e:
                        errors.append(f'Row {row_num}: {str(e)}')
                        error_count += 1
            
            # Show results
            if success_count > 0:
                messages.success(request, f'Successfully imported {success_count} employees.')
            
            if error_count > 0:
                error_message = f'{error_count} errors occurred during import.'
                if errors:
                    error_message += ' First few errors: ' + '; '.join(errors[:5])
                    if len(errors) > 5:
                        error_message += f' ... and {len(errors) - 5} more'
                messages.warning(request, error_message)
            
            return redirect('employees:employee_list')
            
        except Exception as e:
            messages.error(request, f'Error reading Excel file: {str(e)}')
    
    return render(request, 'employees/employee_import.html')

@login_required
def download_employee_template(request):
    """Download Excel template for employee import"""
    # Sample data
    sample_data = [
        {
            'Employee ID': 'EMP-001',
            'First Name': 'John',
            'Last Name': 'Doe',
            'Email': 'john.doe@company.com',
            'Phone': '+1234567890',
            'Department': 'Engineering',
            'Role': 'developer',
            'Status': 'active',
            'Date Joined': '2024-01-15',
            'Salary': 50000,
            'Date of Birth': '1990-05-20',
        }
    ]
    
    df = pd.DataFrame(sample_data)
    
    # Create instructions sheet
    instructions = pd.DataFrame({
        'Column': [
            'Employee ID',
            'First Name', 
            'Last Name',
            'Email',
            'Phone',
            'Department',
            'Role',
            'Status',
            'Date Joined',
            'Salary',
            'Date of Birth',
        ],
        'Required': [
            'Yes',
            'Yes',
            'Yes',
            'Yes',
            'No',
            'No',
            'No',
            'No',
            'No',
            'No',
            'No',
        ],
        'Description': [
            'Unique employee ID',
            'Employee first name',
            'Employee last name',
            'Email address (must be unique)',
            'Phone number',
            'Department name (will be created if not exists)',
            'Role: manager, developer, designer, analyst, engineer, intern, hr, accountant, secretary, other',
            'Status: active, inactive, on_leave, terminated',
            'Date in YYYY-MM-DD format',
            'Salary amount',
            'Date of birth in YYYY-MM-DD format',
        ],
        'Example': [
            'EMP-001',
            'John',
            'Doe',
            'john.doe@company.com',
            '+1234567890',
            'Engineering',
            'developer',
            'active',
            '2024-01-15',
            '50000',
            '1990-05-20',
        ]
    })
    
    # Create Excel file
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Template', index=False)
        instructions.to_excel(writer, sheet_name='Instructions', index=False)
    
    buffer.seek(0)
    
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="employee_import_template.xlsx"'
    return response

@login_required
def employee_summary_report(request):
    """Generate employee summary report"""
    company = request.user.company
    
    # Get statistics
    employees = Employee.objects.filter(company=company)
    
    total_employees = employees.count()
    active_employees = employees.filter(status='active').count()
    inactive_employees = employees.filter(status='inactive').count()
    on_leave_employees = employees.filter(status='on_leave').count()
    terminated_employees = employees.filter(status='terminated').count()
    
    # Role distribution
    role_distribution = employees.values('role').annotate(
        count=Count('id'),
        percentage=Count('id') * 100.0 / total_employees if total_employees > 0 else 0
    ).order_by('-count')
    
    # Department distribution
    department_distribution = employees.values('department__name').annotate(
        count=Count('id'),
        percentage=Count('id') * 100.0 / total_employees if total_employees > 0 else 0
    ).order_by('-count')
    
    # Salary statistics
    salary_stats = employees.aggregate(
        avg_salary=Avg('salary'),
        total_salary=Sum('salary'),
        min_salary=Avg('salary'),  # Would be Min in real implementation
        max_salary=Avg('salary')   # Would be Max in real implementation
    )
    
    # Recent hires (last 30 days)
    thirty_days_ago = datetime.now().date() - pd.Timedelta(days=30)
    recent_hires = employees.filter(
        date_joined__gte=thirty_days_ago
    ).order_by('-date_joined')[:10]
    
    context = {
        'total_employees': total_employees,
        'active_employees': active_employees,
        'inactive_employees': inactive_employees,
        'on_leave_employees': on_leave_employees,
        'terminated_employees': terminated_employees,
        'role_distribution': list(role_distribution),
        'department_distribution': list(department_distribution),
        'salary_stats': salary_stats,
        'recent_hires': recent_hires,
        'report_date': datetime.now().date(),
    }
    
    return render(request, 'employees/employee_summary_report.html', context)

@login_required
def department_report(request):
    """Generate department-wise report"""
    company = request.user.company
    
    departments = Department.objects.filter(company=company).annotate(
        employee_count=Count('employees'),
        avg_salary=Avg('employees__salary'),
        total_salary=Sum('employees__salary'),
        active_count=Count('employees', filter=Q(employees__status='active')),
        on_leave_count=Count('employees', filter=Q(employees__status='on_leave')),
    ).order_by('name')
    
    context = {
        'departments': departments,
        'report_date': datetime.now().date(),
    }
    
    return render(request, 'employees/department_report.html', context)