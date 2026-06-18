from django.urls import reverse
from .models import KadoyaUser, UserRole

class AuthService:
    @staticmethod
    def get_user_dashboard_url(user: KadoyaUser) -> str:
        """
        Retourne l'URL de redirection post-login selon le rôle.
        Pour l'instant, tout le monde va sur la home (/).
        """
        if user.role == UserRole.ADMIN:
            return '/kadmin/'
        elif user.role == UserRole.ARTISAN:
            return reverse('artisan:dashboard')
        return reverse('core:home')
