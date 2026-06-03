from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from apps.core.models import TimeStampedModel
from .managers import KadoyaUserManager

class UserRole(models.TextChoices):
    CLIENT   = 'client',   'Client'
    ARTISAN  = 'artisan',  'Artisan'
    ADMIN    = 'admin',    'Administrateur'

class KadoyaUser(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    """
    Modèle utilisateur personnalisé utilisant l'email comme identifiant unique.
    """
    email        = models.EmailField(unique=True)
    first_name   = models.CharField(max_length=100)
    last_name    = models.CharField(max_length=100)
    phone        = models.CharField(max_length=20, blank=True)
    avatar       = models.ImageField(upload_to='avatars/', blank=True, null=True)
    
    role         = models.CharField(
        max_length=10, 
        choices=UserRole.choices,
        default=UserRole.CLIENT
    )
    
    is_active    = models.BooleanField(default=True)
    is_staff     = models.BooleanField(default=False)
    
    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    objects = KadoyaUserManager()
    
    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_client(self) -> bool:
        return self.role == UserRole.CLIENT
    
    @property
    def is_artisan(self) -> bool:
        return self.role == UserRole.ARTISAN

    def __str__(self) -> str:
        return self.email
