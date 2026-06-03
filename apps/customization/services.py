import os
from io import BytesIO
from decimal import Decimal
from django.core.files.base import ContentFile
from django.utils import timezone
from django.shortcuts import get_object_or_404
from PIL import Image
from apps.catalogue.models import Product
from .models import CustomizationSession, FrameOption, EngravingFont

class CustomizationService:

    @staticmethod
    def get_or_create_session(
        product: Product,
        request
    ) -> CustomizationSession:
        """
        Récupère une session en cours pour ce produit+utilisateur/session,
        ou en crée une nouvelle.
        Priorité : session utilisateur connecté > session anonyme par session_key.
        """
        if not request.session.session_key:
            request.session.create()
        
        session_key = request.session.session_key
        user = request.user if request.user.is_authenticated else None
        
        # Tentative de récupération d'une session IN_PROGRESS
        if user:
            session = CustomizationSession.objects.filter(
                product=product, user=user, status=CustomizationSession.SessionStatus.IN_PROGRESS
            ).first()
        else:
            session = CustomizationSession.objects.filter(
                product=product, session_key=session_key, status=CustomizationSession.SessionStatus.IN_PROGRESS
            ).first()
            
        if not session:
            session = CustomizationSession.objects.create(
                product=product,
                user=user,
                session_key=session_key,
                status=CustomizationSession.SessionStatus.IN_PROGRESS
            )
            
        return session

    @staticmethod
    def save_photo(
        session: CustomizationSession,
        photo_file
    ) -> CustomizationSession:
        """
        1. Sauvegarde le fichier original
        2. Génère une miniature
        3. Met à jour session.current_step = 2
        """
        session.uploaded_photo = photo_file
        
        # Générer miniature
        thumb_content = CustomizationService._generate_thumbnail(photo_file)
        thumb_name = f"thumb_{os.path.basename(photo_file.name)}"
        session.uploaded_photo_thumb.save(thumb_name, thumb_content, save=False)
        
        session.current_step = 2
        session.save()
        return session

    @staticmethod
    def _generate_thumbnail(image_field, max_size: tuple = (400, 400)) -> ContentFile:
        """
        Ouvre l'image Pillow, applique un crop centré (thumbnail préserve le ratio),
        convertit en JPEG qualité 85, retourne un ContentFile prêt à sauvegarder.
        """
        img = Image.open(image_field)
        
        # Crop centré pour un ratio carré si nécessaire (facultatif selon les besoins, 
        # mais ici on fait un thumbnail qui préserve le ratio ou crop ?)
        # On va faire un thumbnail qui rentre dans 400x400
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        temp_handle = BytesIO()
        img_format = 'JPEG' if img.mode != 'RGBA' else 'PNG'
        img.save(temp_handle, format=img_format, quality=85)
        temp_handle.seek(0)
        
        return ContentFile(temp_handle.read())

    @staticmethod
    def save_frame_selection(
        session: CustomizationSession,
        frame_option: FrameOption
    ) -> CustomizationSession:
        """
        Sauvegarde le choix de cadre, calcule le prix final
        et passe à l'étape 3.
        """
        session.frame_option = frame_option
        session.compute_price()
        session.current_step = 3
        session.save()
        return session

    @staticmethod
    def save_engraving(
        session: CustomizationSession,
        text: str,
        position: str,
        font: EngravingFont | None
    ) -> CustomizationSession:
        """
        Sauvegarde le texte gravé (peut être vide).
        Passe à l'étape 4 (aperçu).
        """
        session.engraving_text = text
        session.engraving_position = position
        session.font = font
        session.current_step = 4
        session.save()
        return session

    @staticmethod
    def complete_session(session: CustomizationSession) -> CustomizationSession:
        """
        Marque la session comme COMPLETED.
        """
        session.status = CustomizationSession.SessionStatus.COMPLETED
        session.save()
        return session

    @staticmethod
    def abandon_old_sessions(user) -> None:
        """
        Marque comme ABANDONED toutes les sessions IN_PROGRESS
        datant de plus de 7 jours pour cet utilisateur.
        """
        from datetime import timedelta
        limit = timezone.now() - timedelta(days=7)
        CustomizationSession.objects.filter(
            user=user, 
            status=CustomizationSession.SessionStatus.IN_PROGRESS,
            created_at__lt=limit
        ).update(status=CustomizationSession.SessionStatus.ABANDONED)

    @staticmethod
    def track_customization_behavior(request, product: Product) -> None:
        """
        Enregistre dans la session que l'utilisateur a personnalisé ce produit.
        """
        customized = request.session.get('customized_products', [])
        entry = {
            'product_id': product.pk,
            'category_id': product.category_id,
            'timestamp': timezone.now().isoformat(),
        }
        # Éviter les doublons récents (même produit)
        customized = [
            c for c in customized
            if not (c['product_id'] == product.pk)
        ]
        customized.append(entry)
        request.session['customized_products'] = customized[-10:]
        request.session.modified = True
