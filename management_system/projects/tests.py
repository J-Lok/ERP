from datetime import date, timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from accounts.test_factories import create_test_company
from accounts.models import User
from employees.models import Employee
from projects.models import Project, SousTache, CommentaireTache


class ProjectsModelTests(TestCase):
    def setUp(self):
        self.company = create_test_company(name="InnoDev", domain="innodev")
        self.user = User.objects.create_user(
            email="pm@innodev.io",
            password="password123",
            company=self.company,
            role="manager",
        )
        self.employee = Employee.objects.get(user=self.user)
        self.project = Project.objects.create(
            company=self.company,
            name="ERP Overhaul",
            description="Rebuilding the ERP architecture",
            budget=Decimal("50000.00"),
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            manager=self.employee,
            created_by=self.user,
        )

    def test_project_creation_and_attributes(self):
        self.assertEqual(str(self.project), "ERP Overhaul (InnoDev)")
        self.assertEqual(self.project.completion_percentage, 0)
        self.assertEqual(self.project.task_count, 0)
        self.assertFalse(self.project.is_overdue)

    def test_project_date_validation(self):
        invalid_project = Project(
            company=self.company,
            name="Invalid Dates",
            budget=Decimal("1000.00"),
            start_date=date.today(),
            end_date=date.today() - timedelta(days=5),
        )
        with self.assertRaises(ValidationError):
            invalid_project.full_clean()

    def test_is_overdue_property(self):
        self.project.end_date = date.today() - timedelta(days=1)
        self.project.status = "in_progress"
        self.project.save()
        self.assertTrue(self.project.is_overdue)

        # Completed project is not overdue even if end_date has passed
        self.project.status = "completed"
        self.project.save()
        self.assertFalse(self.project.is_overdue)

    def test_subtask_creation_and_status_transitions(self):
        task = SousTache.objects.create(
            company=self.company,
            projet=self.project,
            titre="Database Schema Design",
            assigne_a=self.employee,
            status="a_faire",
        )
        self.assertEqual(task.completion_percentage, 0)

        # Transition to in progress
        task.change_status("en_cours")
        task.refresh_from_db()
        self.assertEqual(task.status, "en_cours")

        # Transition to done
        task.change_status("termine")
        task.refresh_from_db()
        self.assertEqual(task.status, "termine")
        self.assertEqual(task.completion_percentage, 100)

    def test_project_progress_aggregation(self):
        task1 = SousTache.objects.create(
            company=self.company,
            projet=self.project,
            titre="Task 1",
            completion_percentage=100,
            status="termine",
        )
        task2 = SousTache.objects.create(
            company=self.company,
            projet=self.project,
            titre="Task 2",
            completion_percentage=50,
            status="en_cours",
        )

        self.project.update_completion_from_subtasks()
        self.project.refresh_from_db()
        # Average of 100 and 50 is 75
        self.assertEqual(self.project.completion_percentage, 75)

    def test_task_comment_creation(self):
        task = SousTache.objects.create(
            company=self.company,
            projet=self.project,
            titre="Task with Comments",
        )
        comment = CommentaireTache.objects.create(
            company=self.company,
            tache=task,
            auteur=self.user,
            contenu="Looks great, proceed with deployment.",
        )
        self.assertEqual(comment.tache, task)
        self.assertIn("pm@innodev.io", str(comment))

    def test_tenant_project_isolation(self):
        other_company = create_test_company(name="OtherCo", domain="otherco")
        other_project = Project.objects.create(
            company=other_company,
            name="ERP Overhaul",  # Same name in different company is permitted
            budget=Decimal("10000.00"),
            start_date=date.today(),
            end_date=date.today() + timedelta(days=10),
        )
        company_projects = Project.objects.filter(company=self.company)
        self.assertIn(self.project, company_projects)
        self.assertNotIn(other_project, company_projects)
