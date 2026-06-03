from django.urls import path
from apps.dashboard.views import (
    AdminOverviewView, AdminOrderListView, AdminCustomOrderListView, AdminOrderDetailView,
    AdminProductListView, AdminProductPendingView, AdminValidateProductView, AdminUpdateStockView,
    AdminPromoListView, AdminPromoCreateView, AdminPromoEditView, AdminTogglePromoView,
    AdminArtisanListView, AdminVerifyArtisanView, AdminWithdrawalListView, AdminProcessWithdrawalView,
    AdminNotificationListView, AdminMarkNotifReadView, AdminMarkAllNotifsReadView,
)
from apps.reviews.views import (
    AdminReviewModerationView, AdminReviewApproveView, AdminReviewRejectView
)

app_name = 'dashboard'

urlpatterns = [

    # Overview
    path('', AdminOverviewView.as_view(), name='overview'),

    # Commandes
    path('commandes/',
         AdminOrderListView.as_view(), name='order_list'),
    path('commandes/personnalisees/',
         AdminCustomOrderListView.as_view(), name='custom_orders'),
    path('commandes/<int:pk>/',
         AdminOrderDetailView.as_view(), name='order_detail'),

    # Produits & stock
    path('produits/',
         AdminProductListView.as_view(), name='product_list'),
    path('produits/en-attente/',
         AdminProductPendingView.as_view(), name='products_pending'),
    path('produits/<int:pk>/valider/',
         AdminValidateProductView.as_view(), name='product_validate'),
    path('produits/stock/',
         AdminUpdateStockView.as_view(), name='update_stock'),

    # Promotions
    path('promos/',
         AdminPromoListView.as_view(), name='promo_list'),
    path('promos/nouveau/',
         AdminPromoCreateView.as_view(), name='promo_create'),
    path('promos/<int:pk>/modifier/',
         AdminPromoEditView.as_view(), name='promo_edit'),
    path('promos/<int:pk>/toggle/',
         AdminTogglePromoView.as_view(), name='promo_toggle'),

    # Artisans
    path('artisans/',
         AdminArtisanListView.as_view(), name='artisan_list'),
    path('artisans/<int:pk>/verifier/',
         AdminVerifyArtisanView.as_view(), name='artisan_verify'),
    path('artisans/retraits/',
         AdminWithdrawalListView.as_view(), name='withdrawals'),
    path('artisans/retraits/<int:pk>/traiter/',
         AdminProcessWithdrawalView.as_view(), name='withdrawal_process'),

    # Notifications
    path('notifications/',
         AdminNotificationListView.as_view(), name='notification_list'),
    path('notifications/<int:pk>/lue/',
         AdminMarkNotifReadView.as_view(), name='notif_mark_read'),
    path('notifications/tout-lire/',
         AdminMarkAllNotifsReadView.as_view(), name='notif_mark_all_read'),

    # Modération avis
    path('avis/moderation/',
         AdminReviewModerationView.as_view(), name='review_moderation'),
    path('avis/<int:pk>/approuver/',
         AdminReviewApproveView.as_view(), name='review_approve'),
    path('avis/<int:pk>/rejeter/',
         AdminReviewRejectView.as_view(), name='review_reject'),
]
