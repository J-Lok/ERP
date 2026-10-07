from django.db import migrations, models
import django.db.models.deletion


# Old Employee.role codes → human-readable JobRole name. Mirrors the
# ROLE_CHOICES that used to live on the Employee model before roles became
# a freely-creatable, company-scoped lookup table.
OLD_ROLE_LABELS = {
    'manager': 'Manager',
    'developer': 'Developer',
    'designer': 'Designer',
    'analyst': 'Analyst',
    'engineer': 'Engineer',
    'intern': 'Intern',
    'hr': 'Human Resource',
    'accountant': 'Accountant',
    'secretary': 'Secretary',
    'project_manager': 'Project Manager',
    'stock_manager': 'Stock Manager',
    'other': 'Other',
}


def migrate_roles_forward(apps, schema_editor):
    Employee = apps.get_model('employees', 'Employee')
    JobRole = apps.get_model('employees', 'JobRole')

    role_cache = {}  # (company_id, name) -> JobRole instance

    for employee in Employee.objects.exclude(role_code='').select_related('company'):
        label = OLD_ROLE_LABELS.get(employee.role_code, employee.role_code)
        key = (employee.company_id, label)
        role = role_cache.get(key)
        if role is None:
            role, _ = JobRole.objects.get_or_create(
                company_id=employee.company_id, name=label,
            )
            role_cache[key] = role
        employee.role = role
        employee.save(update_fields=['role'])


def migrate_roles_backward(apps, schema_editor):
    Employee = apps.get_model('employees', 'Employee')
    label_to_code = {v: k for k, v in OLD_ROLE_LABELS.items()}

    for employee in Employee.objects.select_related('role'):
        if employee.role:
            employee.role_code = label_to_code.get(employee.role.name, 'other')
            employee.save(update_fields=['role_code'])


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0006_alter_employee_role'),
    ]

    operations = [
        migrations.CreateModel(
            name='JobRole',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='job_roles', to='accounts.company')),
            ],
            options={
                'ordering': ['name'],
                'unique_together': {('company', 'name')},
            },
        ),
        migrations.RemoveIndex(
            model_name='employee',
            name='employees_e_company_a104e9_idx',
        ),
        migrations.RenameField(
            model_name='employee',
            old_name='role',
            new_name='role_code',
        ),
        migrations.AddField(
            model_name='employee',
            name='role',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='employees', to='employees.jobrole'),
        ),
        migrations.RunPython(migrate_roles_forward, migrate_roles_backward),
        migrations.RemoveField(
            model_name='employee',
            name='role_code',
        ),
        migrations.AddIndex(
            model_name='employee',
            index=models.Index(fields=['company', 'role'], name='employees_company_role_idx'),
        ),
    ]
