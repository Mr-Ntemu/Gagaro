from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', include('apps.core.urls')),
    path('auth/', include('apps.accounts.urls')),
    path('catalogue/', include('apps.catalogue.urls')),
    path('personnaliser/', include('apps.customization.urls', namespace='customization')),
    path('', include(([
        path('panier/',    include('apps.orders.urls')),
        path('commandes/', include('apps.orders.urls_checkout')),
    ], 'orders'))),
    path('paiement/', include('apps.payments.urls', namespace='payments')),
    path('artisan/', include('apps.artisan.urls', namespace='artisan')),
    path('kadmin/', include('apps.dashboard.urls', namespace='dashboard')),
    path('api/reco/', include('apps.recommendations.urls', namespace='recommendations')),
    path('', include('apps.reviews.urls', namespace='reviews')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
