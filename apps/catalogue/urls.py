from django.urls import path
from . import views

app_name = 'catalogue'

urlpatterns = [
    path('', views.CatalogueListingView.as_view(), name='listing'),
    path('categorie/<slug:slug>/', views.CategoryListingView.as_view(), name='by_category'),
    path('<slug:slug>/', views.ProductDetailView.as_view(), name='detail'),
]
