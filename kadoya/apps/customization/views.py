from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import JsonResponse
from django.urls import reverse
from apps.catalogue.models import Product
from .models import FrameOption, EngravingFont, CustomizationSession
from .forms import PhotoUploadForm, FrameSelectionForm, EngravingForm
from .services import CustomizationService

class CustomizationWizardView(View):
    """
    Vue principale du tunnel de personnalisation.
    GET  /personnaliser/<product_slug>/       → affiche le wizard à l'étape courante
    """

    def get(self, request, product_slug: str):
        product = get_object_or_404(Product, slug=product_slug,
                                     status='active', is_customizable=True)
        session = CustomizationService.get_or_create_session(product, request)
        CustomizationService.track_customization_behavior(request, product)

        steps = [
            (1, 'Photo'),
            (2, 'Cadre'),
            (3, 'Gravure'),
            (4, 'Aperçu'),
        ]

        context = {
            'product':      product,
            'session':      session,
            'steps':        steps,
            'frame_options': FrameOption.objects.filter(
                               product=product, is_available=True
                             ).order_by('order'),
            'fonts':        EngravingFont.objects.filter(is_active=True),
            'upload_form':  PhotoUploadForm(),
            'frame_form':   FrameSelectionForm(product=product),
            'engraving_form': EngravingForm(),
        }
        return render(request, 'customization/wizard.html', context)


class UploadPhotoView(View):
    """POST AJAX — Étape 1 : upload de photo."""

    def post(self, request, product_slug: str):
        product = get_object_or_404(Product, slug=product_slug, is_customizable=True)
        form    = PhotoUploadForm(request.POST, request.FILES)

        if not form.is_valid():
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

        session  = CustomizationService.get_or_create_session(product, request)
        session  = CustomizationService.save_photo(session, form.cleaned_data['photo'])

        return JsonResponse({
            'success':     True,
            'next_step':   2,
            'thumb_url':   request.build_absolute_uri(session.uploaded_photo_thumb.url),
            'session_id':  session.pk,
        })


class SelectFrameView(View):
    """POST AJAX — Étape 2 : sélection du cadre."""

    def post(self, request, product_slug: str):
        product = get_object_or_404(Product, slug=product_slug, is_customizable=True)
        form    = FrameSelectionForm(product=product, data=request.POST)

        if not form.is_valid():
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

        session       = CustomizationService.get_or_create_session(product, request)
        frame_option  = form.cleaned_data['frame_option']
        session       = CustomizationService.save_frame_selection(session, frame_option)

        return JsonResponse({
            'success':         True,
            'next_step':       3,
            'computed_price':  str(session.computed_price),
            'frame_label':     frame_option.label,
        })


class SaveEngravingView(View):
    """POST AJAX — Étape 3 : texte gravé (optionnel)."""

    def post(self, request, product_slug: str):
        product = get_object_or_404(Product, slug=product_slug, is_customizable=True)
        form    = EngravingForm(request.POST)

        if not form.is_valid():
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

        session = CustomizationService.get_or_create_session(product, request)
        session = CustomizationService.save_engraving(
            session,
            text     = form.cleaned_data.get('engraving_text', ''),
            position = form.cleaned_data.get('engraving_position', 'bottom'),
            font     = form.cleaned_data.get('font'),
        )

        return JsonResponse({'success': True, 'next_step': 4})


class CompleteCustomizationView(View):
    """POST AJAX — Étape 4 : validation finale → prêt pour le panier."""

    def post(self, request, product_slug: str):
        product = get_object_or_404(Product, slug=product_slug, is_customizable=True)
        session = CustomizationService.get_or_create_session(product, request)

        if not session.is_complete:
            return JsonResponse({
                'success': False,
                'error': 'La personnalisation est incomplète. Photo et cadre requis.'
            }, status=400)

        session = CustomizationService.complete_session(session)

        return JsonResponse({
            'success':     True,
            'session_id':  session.pk,
            'redirect_url': reverse('catalogue:detail', kwargs={'slug': product_slug}),
            # TODO Sprint 4 : rediriger vers le panier avec session liée
        })
