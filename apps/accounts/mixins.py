from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.contrib import messages


class ArtisanRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Mixin à hériter dans toutes les vues du dashboard artisan.
    Vérifie :
    1. L'utilisateur est connecté (LoginRequiredMixin)
    2. L'utilisateur a le rôle 'artisan' (UserPassesTestMixin)
    Redirige vers l'accueil avec un message d'erreur si non autorisé.
    """

    def test_func(self) -> bool:
        return self.request.user.is_authenticated and self.request.user.is_artisan

    def handle_no_permission(self):
        messages.error(
            self.request,
            "Accès refusé. Cet espace est réservé aux artisans Kadoya."
        )
        return redirect('core:home')


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Mixin pour toutes les vues du dashboard admin Kadoya.
    Vérifie que l'utilisateur a le rôle 'admin' OU is_staff=True.
    """

    def test_func(self) -> bool:
        user = self.request.user
        return user.is_authenticated and (user.role == 'admin' or user.is_staff)

    def handle_no_permission(self):
        messages.error(
            self.request,
            "Accès refusé. Espace réservé à l'équipe Kadoya."
        )
        return redirect('core:home')
