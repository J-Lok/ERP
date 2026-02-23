from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Avg, Sum
from django.db import transaction
from django.http import HttpResponse
from datetime import datetime
import pandas as pd
import io

from .models import Employee, Department
from .forms import EmployeeForm, DepartmentForm
from accounts.models import User


# =====================
# Employee Views
# =====================

@login_required
def employee_list(request):
    """Display all employees with filters and search"""
    company = request.user.company
    employees = Employee.objects.filter(company=company).select_related('user', 'department')

    # Filters
    query = request.GET.get('q', '').strip()
    if query:
        employees = employees.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(employee_id__icontains=query) |
            Q(user__email__icontains=query) |
            Q(department__name__icontains=query)
        )

    department_id = request.GET.get('department')
    if department_id:
        employees = employees.filter(department_id=department_id)

    status = request.GET.get('status')
    if status:
        employees = employees.filter(status=status)

    role = request.GET.get('role')
    if role:
        employees = employees.filter(role=role)

    # Stats
    total_employees = employees.count()
    active_employees = employees.filter(status='active').count()
    on_leave_employees = employees.filter(status='on_leave').count()
    roles = employees.values_list('role', flat=True).distinct()
    departments = Department.objects.filter(company=company).order_by('name')

    context = {
        'employees': employees.order_by('-created_at'),
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
    return render(request, 'employees/employee_detail.html', {'employee': employee})


@login_required
def employee_create(request):
    """Add new employee"""
    company = request.user.company

    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES, company=company)
        if form.is_valid():
            employee = form.save()
            messages.success(request, f'Employee {employee.employee_id} created successfully!')
            return redirect('employees:employee_list')
    else:
        form = EmployeeForm(company=company)

    return render(request, 'employees/employee_form.html', {'form': form, 'title': 'Add New Employee'})


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

    return render(request, 'employees/employee_form.html', {'form': form, 'employee': employee, 'title': 'Edit Employee'})


@login_required
def employee_delete(request, pk):
    """Delete an employee"""
    company = request.user.company
    employee = get_object_or_404(Employee, pk=pk, company=company)

    if request.method == 'POST':
        employee_id = employee.employee_id
        employee_name = employee.user.get_full_name()
        employee.delete()
        messages.success(request, f'Employee {employee_id} - {employee_name} deleted successfully!')
        return redirect('employees:employee_list')

    return render(request, 'employees/employee_confirm_delete.html', {'employee': employee})


# =====================
# Department Views
# =====================

@login_required
def department_list(request):
    """List all departments with employee counts"""
    company = request.user.company
    departments = Department.objects.filter(company=company).annotate(employee_count=Count('employees')).order_by('name')
    return render(request, 'employees/department_list.html', {'departments': departments})


@login_required
def department_create(request):
    """Add a new department"""
    company = request.user.company
    if request.method == 'POST':
        form = DepartmentForm(request.POST, company=company)
        if form.is_valid():
            department = form.save()
            messages.success(request, f'Department "{department.name}" created successfully!')
            return redirect('employees:department_list')
    else:
        form = DepartmentForm(company=company)

    return render(request, 'employees/department_form.html', {'form': form, 'title': 'Add New Department'})


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

    return render(request, 'employees/department_form.html', {'form': form, 'department': department, 'title': 'Edit Department'})


@login_required
def department_delete(request, pk):
    """Delete a department"""
    company = request.user.company
    department = get_object_or_404(Department, pk=pk, company=company)

    if request.method == 'POST':
        department_name = department.name
        department.delete()
        messages.success(request, f'Department "{department_name}" deleted successfully!')
        return redirect('employees:department_list')

    return render(request, 'employees/department_confirm_delete.html', {'department': department})


# =====================
# Employee Import/Export
# =====================

@login_required
def employee_export(request):
    """Export employees to Excel"""
    company = request.user.company
    employees = Employee.objects.filter(company=company).select_related('user', 'department')

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
            'Salary': float(emp.salary or 0),
            'Date of Birth': emp.date_of_birth.strftime('%Y-%m-%d') if emp.date_of_birth else '',
        })

    df = pd.DataFrame(data)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Employees', index=False)
        worksheet = writer.sheets['Employees']
        for column in worksheet.columns:
            max_length = max(len(str(cell.value)) for cell in column if cell.value) + 2
            worksheet.column_dimensions[column[0].column_letter].width = min(max_length, 50)
    buffer.seek(0)

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
            messages.error(request, 'Please upload a valid Excel file (.xlsx or .xls).')
            return redirect('employees:employee_import')

        try:
            df = pd.read_excel(excel_file)
            required_columns = ['Employee ID', 'First Name', 'Last Name', 'Email']
            missing = [col for col in required_columns if col not in df.columns]
            if missing:
                messages.error(request, f'Missing columns: {", ".join(missing)}')
                return redirect('employees:employee_import')

            success_count = 0
            errors = []

            with transaction.atomic():
                for idx, row in df.iterrows():
                    row_num = idx + 2
                    try:
                        emp_id = str(row['Employee ID']).strip()
                        first_name = str(row['First Name']).strip()
                        last_name = str(row['Last Name']).strip()
                        email = str(row['Email']).strip().lower()
                        salary = row.get('Salary') or 0

                        if not all([emp_id, first_name, last_name, email]):
                            errors.append(f'Row {row_num}: Missing required fields')
                            continue

                        if Employee.objects.filter(company=company, employee_id=emp_id).exists():
                            errors.append(f'Row {row_num}: Employee ID {emp_id} exists')
                            continue

                        user = User.objects.filter(email=email, company=company).first()
                        if not user:
                            user = User.objects.create_user(
                                email=email,
                                password='TempPassword123',
                                first_name=first_name,
                                last_name=last_name,
                                company=company
                            )

                        department = None
                        if 'Department' in df.columns and pd.notna(row['Department']):
                            dept_name = str(row['Department']).strip()
                            department, _ = Department.objects.get_or_create(
                                name=dept_name,
                                company=company,
                                defaults={'description': f'Department for {dept_name}'}
                            )

                        employee = Employee(
                            company=company,
                            user=user,
                            employee_id=emp_id,
                            department=department,
                            role=row.get('Role', 'other'),
                            status=row.get('Status', 'active'),
                            date_joined=datetime.now().date(),
                            salary=salary
                        )

                        if 'Phone' in df.columns and pd.notna(row['Phone']):
                            user.phone = str(row['Phone']).strip()
                            user.save()

                        if 'Date of Birth' in df.columns and pd.notna(row['Date of Birth']):
                            employee.date_of_birth = pd.to_datetime(row['Date of Birth']).date()

                        employee.save()
                        success_count += 1

                    except Exception as e:
                        errors.append(f'Row {row_num}: {str(e)}')

            if success_count:
                messages.success(request, f'Successfully imported {success_count} employees.')
            if errors:
                err_msg = f'{len(errors)} errors occurred. First few: {"; ".join(errors[:5])}'
                messages.warning(request, err_msg)

            return redirect('employees:employee_list')

        except Exception as e:
            messages.error(request, f'Error reading Excel file: {str(e)}')

    return render(request, 'employees/employee_import.html')


@login_required
def download_employee_template(request):
    """Download Excel template for employee import"""
    sample = [{
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
    }]

    df = pd.DataFrame(sample)
    instructions = pd.DataFrame({
        'Column': ['Employee ID', 'First Name', 'Last Name', 'Email', 'Phone', 'Department', 'Role', 'Status', 'Date Joined', 'Salary', 'Date of Birth'],
        'Required': ['Yes', 'Yes', 'Yes', 'Yes', 'No', 'No', 'No', 'No', 'No', 'No', 'No'],
        'Description': [
            'Unique employee ID',
            'First name',
            'Last name',
            'Email',
            'Phone number',
            'Department name',
            'Role: manager, developer, ...',
            'Status: active, inactive, ...',
            'YYYY-MM-DD',
            'Salary amount',
            'YYYY-MM-DD'
        ],
        'Example': ['EMP-001', 'John', 'Doe', 'john.doe@company.com', '+1234567890', 'Engineering', 'developer', 'active', '2024-01-15', 50000, '1990-05-20']
    })

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

from django.db.models import Min, Max

@login_required
def employee_summary_report(request):
    """Generate summary report for all employees in the company"""
    company = request.user.company
    employees = Employee.objects.filter(company=company)

    total_employees = employees.count()
    active_employees = employees.filter(status='active').count()
    inactive_employees = employees.filter(status='inactive').count()
    on_leave_employees = employees.filter(status='on_leave').count()
    terminated_employees = employees.filter(status='terminated').count()

    # Role distribution with percentage
    role_distribution = []
    role_counts = employees.values('role').annotate(count=Count('id'))
    for rc in role_counts:
        percentage = (rc['count'] / total_employees * 100) if total_employees else 0
        role_distribution.append({
            'role': rc['role'],
            'count': rc['count'],
            'percentage': round(percentage, 2)
        })

    # Department distribution with percentage
    department_distribution = []
    dept_counts = employees.values('department__name').annotate(count=Count('id'))
    for dc in dept_counts:
        percentage = (dc['count'] / total_employees * 100) if total_employees else 0
        department_distribution.append({
            'department': dc['department__name'] or 'Unassigned',
            'count': dc['count'],
            'percentage': round(percentage, 2)
        })

    # Salary statistics
    salary_stats = employees.aggregate(
        avg_salary=Avg('salary'),
        total_salary=Sum('salary'),
        min_salary=Min('salary'),
        max_salary=Max('salary')
    )

    # Recent hires (last 30 days)
    thirty_days_ago = datetime.now().date() - pd.Timedelta(days=30)
    recent_hires = employees.filter(date_joined__gte=thirty_days_ago).order_by('-date_joined')[:10]

    context = {
        'total_employees': total_employees,
        'active_employees': active_employees,
        'inactive_employees': inactive_employees,
        'on_leave_employees': on_leave_employees,
        'terminated_employees': terminated_employees,
        'role_distribution': role_distribution,
        'department_distribution': department_distribution,
        'salary_stats': salary_stats,
        'recent_hires': recent_hires,
        'report_date': datetime.now().date(),
    }
    return render(request, 'employees/employee_summary_report.html', context)


@login_required
def department_report(request):
    """Generate detailed department-wise report"""
    company = request.user.company
    departments = Department.objects.filter(company=company).annotate(
        employee_count=Count('employees'),
        avg_salary=Avg('employees__salary'),
        total_salary=Sum('employees__salary'),
        min_salary=Min('employees__salary'),
        max_salary=Max('employees__salary'),
        active_count=Count('employees', filter=Q(employees__status='active')),
        on_leave_count=Count('employees', filter=Q(employees__status='on_leave')),
    ).order_by('name')
    
    # Calculate totals
    total_employees = sum(dept.employee_count for dept in departments)
    total_active = sum(dept.active_count or 0 for dept in departments)
    total_on_leave = sum(dept.on_leave_count or 0 for dept in departments)
    total_salary = sum(dept.total_salary or 0 for dept in departments)
    
    context = {
        'departments': departments,
        'report_date': datetime.now().date(),
        'totals': {
            'employees': total_employees,
            'active': total_active,
            'on_leave': total_on_leave,
            'salary': total_salary,
        }
    }
    return render(request, 'employees/department_report.html', context)