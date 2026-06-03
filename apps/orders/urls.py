from django.urls import path
from .views import (
    CartView, 
    AddToCartView, 
    UpdateCartItemView, 
    RemoveFromCartView
)

urlpatterns = [
    path('',                  CartView.as_view(),           name='cart'),
    path('ajouter/',          AddToCartView.as_view(),      name='add_to_cart'),
    path('modifier/<int:item_id>/',
                              UpdateCartItemView.as_view(), name='update_item'),
    path('supprimer/<int:item_id>/',
                              RemoveFromCartView.as_view(), name='remove_item'),
]
