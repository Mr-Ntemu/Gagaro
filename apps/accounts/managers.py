from django.contrib.auth.models import BaseUserManager

class KadoyaUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        """Crée et enregistre un utilisateur avec l'email et le mot de passe donnés."""
        if not email:
            raise ValueError("L'adresse email est obligatoire")
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Crée et enregistre un super-utilisateur avec l'email et le mot de passe donnés."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

    def clients(self):
        """Retourne le queryset filtré pour les utilisateurs ayant le rôle CLIENT."""
        return self.get_queryset().filter(role='client')

    def artisans(self):
        """Retourne le queryset filtré pour les utilisateurs ayant le rôle ARTISAN."""
        return self.get_queryset().filter(role='artisan')
