from datetime import datetime
from .models import Budget, Alert


def static_pages(request):
    if request.user.is_authenticated:
        today = datetime.today()
        unverified_budgets = Budget.objects.filter(verified=1, verifying_user=request.user).count()
        alerts = Alert.objects.filter(date=today, user=request.user).count()
        return {'unverified_budgets_number': unverified_budgets, 'alerts_number': alerts}
    else:
        return {}
