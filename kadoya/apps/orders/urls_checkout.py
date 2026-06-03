from django.urls import path
from .views import CheckoutView, OrderConfirmationView

urlpatterns = [
    path('checkout/',
         CheckoutView.as_view(), name='checkout'),
    path('confirmation/<str:reference>/',
         OrderConfirmationView.as_view(), name='confirmation'),
]
