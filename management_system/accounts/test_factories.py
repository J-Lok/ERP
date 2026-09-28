from accounts.models import Company

def create_test_company(name="Test Company", domain="test-company", contact_email="test@company.com", **kwargs):
    """Helper factory for creating Company instances in tests with all required fields."""
    defaults = {
        'name': name,
        'domain': domain,
        'contact_email': contact_email,
    }
    defaults.update(kwargs)
    return Company.objects.create(**defaults)
