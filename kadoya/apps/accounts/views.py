from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, RedirectView
from django.contrib.auth.views import LoginView as DjangoLoginView, LogoutView as DjangoLogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import login
from .forms import KadoyaUserCreationForm
from .services import AuthService

class RegisterView(CreateView):
    """Vue pour l'inscription d'un nouvel utilisateur avec choix de rôle."""
    template_name = 'accounts/register.html'
    form_class = KadoyaUserCreationForm
    def get_success_url(self):
        return AuthService.get_user_dashboard_url(self.object)

    def form_valid(self, form):
        self.object = form.save()
        login(self.request, self.object, backend='django.contrib.auth.backends.ModelBackend')
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(self.get_success_url())

class LoginView(DjangoLoginView):
    """Vue pour la connexion des utilisateurs par email."""
    template_name = 'accounts/login.html'
    
    def get_success_url(self):
        return AuthService.get_user_dashboard_url(self.request.user)

class LogoutView(DjangoLogoutView):
    """Vue pour la déconnexion (POST uniquement)."""
    http_method_names = ['post'] # Protection CSRF forcee par Django 5+

class ProfileView(LoginRequiredMixin, DetailView):
    """Vue affichant le profil de l'utilisateur connecté."""
    template_name = 'accounts/profile.html'
    context_object_name = 'user'

    def get_object(self):
        return self.request.user
