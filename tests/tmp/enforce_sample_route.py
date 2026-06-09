# Refactored: DB access delegated to a service layer
from services.user_service import list_users


def handle_request(request):
    users = list_users()
    return {"users": users}
