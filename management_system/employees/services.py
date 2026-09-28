from employees.models import Employee


def get_employee_or_none(user):
    """
    Safely retrieve the Employee profile for a user object without throwing DoesNotExist.

    Args:
        user: User instance

    Returns:
        Employee instance or None
    """
    if user is None or not user.is_authenticated:
        return None
    try:
        return getattr(user, 'employee_profile', None)
    except Employee.DoesNotExist:
        return None
