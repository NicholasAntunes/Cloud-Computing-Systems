"""LogBook: a database record of every login, logout and file operation.

The rules for who writes which entry are in docs/API.md "LogBook service".
The admin endpoints (``GET /api/logbook`` with filters, CSV and JSON export)
come next, until 6 Dec (docs/PLAN.md §10).

Package layout:
    service.py  Action, log_event, log_failure, logged, logged_action
"""

from .service import Action, log_event, log_failure, logged, logged_action

__all__ = ["Action", "log_event", "log_failure", "logged", "logged_action"]
