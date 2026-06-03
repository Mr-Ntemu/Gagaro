from django.urls import path
from .views import (
    CustomizationWizardView, 
    UploadPhotoView, 
    SelectFrameView, 
    SaveEngravingView, 
    CompleteCustomizationView
)

app_name = 'customization'

urlpatterns = [
    path('<slug:product_slug>/',
         CustomizationWizardView.as_view(), name='wizard'),

    path('<slug:product_slug>/photo/',
         UploadPhotoView.as_view(), name='upload_photo'),

    path('<slug:product_slug>/cadre/',
         SelectFrameView.as_view(), name='select_frame'),

    path('<slug:product_slug>/texte/',
         SaveEngravingView.as_view(), name='save_engraving'),

    path('<slug:product_slug>/valider/',
         CompleteCustomizationView.as_view(), name='complete'),
]
