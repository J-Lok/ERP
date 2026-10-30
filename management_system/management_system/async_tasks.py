import logging
import threading
from functools import wraps
from django.conf import settings
from django.db import close_old_connections

logger = logging.getLogger(__name__)


def async_task(func):
    """
    Decorator to execute a function asynchronously in a background thread.
    Automatically manages database connection lifecycles (close_old_connections)
    and supports synchronous execution during test runs via ASYNC_TASKS_SYNC=True.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Support running synchronously during tests or when configured
        if getattr(settings, 'ASYNC_TASKS_SYNC', False):
            return func(*args, **kwargs)

        def run():
            close_old_connections()
            try:
                func(*args, **kwargs)
            except Exception as e:
                logger.error("Background task %s failed: %s", func.__name__, e, exc_info=True)
            finally:
                close_old_connections()

        thread = threading.Thread(target=run, daemon=True, name=f"async_{func.__name__}")
        thread.start()
        return thread
    return wrapper


@async_task
def send_email_in_background(company, subject, body, recipient_list, html_message=None):
    """Background task to send emails without blocking the main request thread."""
    from accounts.views import send_company_email
    try:
        send_company_email(company, subject, body, recipient_list, html_message)
    except Exception as e:
        company_name = getattr(company, 'name', company)
        logger.error("send_email_in_background failed for company %s recipients %s: %s", company_name, recipient_list, e, exc_info=True)
