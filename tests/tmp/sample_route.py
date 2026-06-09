# SOC VIOLATION: business logic and DB access inside route handler
from infrastructure.database import query_users


def handle_request(request):
    users = query_users()
    return {"users": users}
