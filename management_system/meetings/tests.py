"""
meetings/tests.py

Unit tests for meetings app.
"""

from django.test import TestCase
from django.utils import timezone
from accounts.models import Company
from employees.models import Employee, Department
from django.contrib.auth.models import User
from .models import Meeting, ActionItem, MeetingNote, MeetingAttachment


class MeetingModelTestCase(TestCase):
    """Test cases for Meeting model."""
    
    def setUp(self):
        self.company = Company.objects.create(name='Test Company', tax_id='12345')
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.department = Department.objects.create(name='Test Dept', company=self.company)
        self.employee = Employee.objects.create(
            user=self.user,
            company=self.company,
            department=self.department,
            phone='1234567890',
            hire_date=timezone.now()
        )
        
        self.meeting = Meeting.objects.create(
            company=self.company,
            title='Test Meeting',
            scheduled_date=timezone.now() + timezone.timedelta(days=1),
            organizer=self.employee,
            created_by=self.user
        )
    
    def test_meeting_creation(self):
        """Test that a meeting can be created."""
        self.assertEqual(self.meeting.title, 'Test Meeting')
        self.assertEqual(self.meeting.status, 'scheduled')
    
    def test_meeting_str(self):
        """Test meeting string representation."""
        expected = f"{self.meeting.title} - {self.meeting.scheduled_date.strftime('%Y-%m-%d %H:%M')}"
        self.assertEqual(str(self.meeting), expected)
    
    def test_mark_meeting_completed(self):
        """Test marking a meeting as completed."""
        self.meeting.mark_completed()
        self.assertEqual(self.meeting.status, 'completed')
        self.assertIsNotNone(self.meeting.actual_start)
        self.assertIsNotNone(self.meeting.actual_end)


class ActionItemModelTestCase(TestCase):
    """Test cases for ActionItem model."""
    
    def setUp(self):
        self.company = Company.objects.create(name='Test Company', tax_id='12345')
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.department = Department.objects.create(name='Test Dept', company=self.company)
        self.employee = Employee.objects.create(
            user=self.user,
            company=self.company,
            department=self.department,
            phone='1234567890',
            hire_date=timezone.now()
        )
        
        self.meeting = Meeting.objects.create(
            company=self.company,
            title='Test Meeting',
            scheduled_date=timezone.now() + timezone.timedelta(days=1),
            organizer=self.employee,
            created_by=self.user
        )
        
        self.action_item = ActionItem.objects.create(
            meeting=self.meeting,
            title='Test Action',
            due_date=timezone.now().date() + timezone.timedelta(days=5),
            assigned_to=self.employee
        )
    
    def test_action_item_creation(self):
        """Test that an action item can be created."""
        self.assertEqual(self.action_item.title, 'Test Action')
        self.assertEqual(self.action_item.status, 'pending')
    
    def test_action_item_is_overdue(self):
        """Test checking if action item is overdue."""
        past_date_action = ActionItem.objects.create(
            meeting=self.meeting,
            title='Past Action',
            due_date=timezone.now().date() - timezone.timedelta(days=1),
            assigned_to=self.employee
        )
        self.assertTrue(past_date_action.is_overdue())
        self.assertFalse(self.action_item.is_overdue())
    
    def test_action_item_mark_completed(self):
        """Test marking an action item as completed."""
        self.action_item.mark_completed()
        self.assertEqual(self.action_item.status, 'completed')
        self.assertEqual(self.action_item.completion_percentage, 100)
        self.assertIsNotNone(self.action_item.actual_completion_date)


class MeetingNoteModelTestCase(TestCase):
    """Test cases for MeetingNote model."""
    
    def setUp(self):
        self.company = Company.objects.create(name='Test Company', tax_id='12345')
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.department = Department.objects.create(name='Test Dept', company=self.company)
        self.employee = Employee.objects.create(
            user=self.user,
            company=self.company,
            department=self.department,
            phone='1234567890',
            hire_date=timezone.now()
        )
        
        self.meeting = Meeting.objects.create(
            company=self.company,
            title='Test Meeting',
            scheduled_date=timezone.now() + timezone.timedelta(days=1),
            organizer=self.employee,
            created_by=self.user
        )
    
    def test_meeting_note_creation(self):
        """Test that meeting notes can be created."""
        note = MeetingNote.objects.create(
            meeting=self.meeting,
            agenda='Test agenda',
            discussion_summary='Test summary',
            last_edited_by=self.user
        )
        self.assertEqual(note.agenda, 'Test agenda')
        self.assertEqual(note.discussion_summary, 'Test summary')
