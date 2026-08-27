from django.urls import path
from .views import (
    InitiatePaymentView,
    PaymentPendingView,
    PaymentStatusView,
    MonetbilNotifyView,
    PaymentSuccessView,
    PaymentFailedView,
)

app_name = 'payments'

urlpatterns = [
    path('initier/<str:reference>/', InitiatePaymentView.as_view(),  name='initiate'),
    path('attente/<str:reference>/', PaymentPendingView.as_view(),   name='pending'),
    path('statut/<str:reference>/',  PaymentStatusView.as_view(),    name='status'),
    path('notify/monetbil/',         MonetbilNotifyView.as_view(),   name='monetbil_notify'),
    path('succes/<str:reference>/',  PaymentSuccessView.as_view(),   name='success'),
    path('echec/<str:reference>/',   PaymentFailedView.as_view(),    name='failed'),
]
