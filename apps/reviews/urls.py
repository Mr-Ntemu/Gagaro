from django.urls import path
from apps.reviews.views import (
    OrderHistoryView, OrderTrackingView, ReviewCreateView, 
    ReviewListAjaxView, ArtisanReplyView
)

app_name = 'reviews'

urlpatterns = [
    # Client — Commandes
    path('commandes/historique/',
         OrderHistoryView.as_view(), name='order_history'),
    path('commandes/suivi/<str:reference>/',
         OrderTrackingView.as_view(), name='order_tracking'),

    # Client — Avis
    path('avis/nouveau/<slug:product_slug>/',
         ReviewCreateView.as_view(), name='review_create'),
    path('avis/produit/<slug:product_slug>/',
         ReviewListAjaxView.as_view(), name='review_list_ajax'),

    # Artisan — Réponse
    path('avis/<int:pk>/repondre/',
         ArtisanReplyView.as_view(), name='artisan_reply'),
]
