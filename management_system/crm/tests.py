from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase
from django.db import IntegrityError
from accounts.models import Company, User
from employees.models import Employee
from crm.models import Contact, Note, Opportunity


class CRMModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name='CRMCo', domain='crmco', contact_email='crmco@example.com'
        )
        self.user = User.objects.create_user(
            email='sales@crmco.io',
            password='password123',
            company=self.company,
            role='manager',
        )
        self.contact = Contact.objects.create(
            company=self.company,
            name='Alice Wonderland',
            email='alice@example.com',
            organization='Wonderland Ltd',
        )

    def test_contact_creation_and_uniqueness(self):
        self.assertEqual(str(self.contact), "Alice Wonderland (CRMCo)")
        with self.assertRaises(IntegrityError):
            Contact.objects.create(
                company=self.company,
                name='Alice Duplicate',
                email='alice@example.com',  # Duplicate email in same company
            )

    def test_contact_notes(self):
        note = Note.objects.create(
            company=self.company,
            contact=self.contact,
            author=self.user,
            note_type='call',
            content='Discussed pricing and contract terms for Q3.',
        )
        self.assertEqual(note.contact, self.contact)
        self.assertIn('[Phone Call]', str(note))

    def test_opportunity_lifecycle_and_pipeline(self):
        opp = Opportunity.objects.create(
            company=self.company,
            contact=self.contact,
            title='Enterprise Cloud Migration',
            value=Decimal('25000.00'),
            stage='prospect',
            follow_up_date=date.today() - timedelta(days=2),
            created_by=self.user,
        )
        self.assertEqual(str(opp), 'Enterprise Cloud Migration (Alice Wonderland)')
        self.assertTrue(opp.is_open)
        self.assertFalse(opp.is_won)
        self.assertTrue(opp.is_overdue_followup)

        # Contact aggregate pipeline value
        self.assertEqual(self.contact.open_opportunities_count, 1)
        self.assertEqual(self.contact.pipeline_value, Decimal('25000.00'))

        # Advance stage
        opp.advance_stage('proposal')
        self.assertEqual(opp.stage, 'proposal')

        opp.advance_stage('won')
        self.assertTrue(opp.is_won)
        self.assertFalse(opp.is_open)
        # Won deals are excluded from open pipeline value
        self.assertEqual(self.contact.open_opportunities_count, 0)
        self.assertEqual(self.contact.pipeline_value, 0)

        # Invalid stage
        with self.assertRaises(ValueError):
            opp.advance_stage('invalid_stage_xyz')

    def test_opportunity_payment_status(self):
        opp = Opportunity.objects.create(
            company=self.company,
            contact=self.contact,
            title='Support Contract',
            value=Decimal('5000.00'),
            stage='won',
        )
        self.assertEqual(opp.payment_status, 'unpaid')
        opp.payment_status = 'invoiced'
        opp.save()
        self.assertEqual(opp.payment_status, 'invoiced')
        opp.payment_status = 'paid'
        opp.save()
        self.assertEqual(opp.payment_status, 'paid')

    def test_tenant_crm_isolation(self):
        other_company = Company.objects.create(
            name='OtherCo', domain='otherco', contact_email='other@otherco.com'
        )
        other_contact = Contact.objects.create(
            company=other_company,
            name='Bob',
            email='bob@otherco.com',
        )
        company_contacts = Contact.objects.filter(company=self.company)
        self.assertIn(self.contact, company_contacts)
        self.assertNotIn(other_contact, company_contacts)
