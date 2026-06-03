from django.urls import path
from .views import (
    ArtisanDashboardView, ArtisanProfileEditView,
    ProductListView, ProductCreateView, ProductEditView,
    ToggleProductStatusView, ProductDeleteView,
    SalesView, ArtisanOrderDetailView, FinancialView
)

app_name = 'artisan'

urlpatterns = [
    # Dashboard
    path('',
         ArtisanDashboardView.as_view(), name='dashboard'),

    # Profil atelier
    path('profil/',
         ArtisanProfileEditView.as_view(), name='profile_edit'),

    # Catalogue produits
    path('produits/',
         ProductListView.as_view(), name='product_list'),
    path('produits/nouveau/',
         ProductCreateView.as_view(), name='product_create'),
    path('produits/<slug:slug>/modifier/',
         ProductEditView.as_view(), name='product_edit'),
    path('produits/<slug:slug>/toggle/',
         ToggleProductStatusView.as_view(), name='product_toggle'),
    path('produits/<slug:slug>/supprimer/',
         ProductDeleteView.as_view(), name='product_delete'),

    # Ventes
    path('ventes/',
         SalesView.as_view(), name='sales'),
    path('commandes/<str:reference>/',
         ArtisanOrderDetailView.as_view(), name='order_detail'),

    # Finances
    path('finances/',
         FinancialView.as_view(), name='financial'),
]
