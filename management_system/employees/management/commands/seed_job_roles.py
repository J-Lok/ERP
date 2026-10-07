from django.core.management.base import BaseCommand

from accounts.models import Company
from employees.models import JobRole, seed_default_job_roles


class Command(BaseCommand):
    """Ensure every company has the default set of job roles.

    Idempotent — only creates whichever default role names are missing for
    each company. Safe to run on every deploy (e.g. alongside `migrate`),
    including the first one, and safe to re-run any time afterwards.
    """

    help = 'Seed the default JobRoles for every company that is missing some of them.'

    def handle(self, *args, **options):
        companies = Company.objects.all()
        total_created = 0

        for company in companies:
            before = JobRole.objects.filter(company=company).count()
            seed_default_job_roles(company)
            created = JobRole.objects.filter(company=company).count() - before
            total_created += created
            if created:
                self.stdout.write(f'{company.name}: added {created} role(s).')

        self.stdout.write(self.style.SUCCESS(
            f'Done — {total_created} role(s) created across {companies.count()} company(ies).'
        ))
