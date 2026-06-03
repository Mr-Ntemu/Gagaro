import time
import logging
from .services import RecommendationService

logger = logging.getLogger(__name__)

class SessionBehaviorMiddleware:
    """
    Middleware Django qui flush les événements comportementaux
    de la session vers la base de données pour les utilisateurs connectés.
    """

    FLUSH_INTERVAL_SECONDS = 300  # 5 minutes

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Flush uniquement pour les utilisateurs connectés sur GET
        if (
            request.method == 'GET'
            and request.user.is_authenticated
            and getattr(request.user, 'is_client', False)  # Pas pour artisans/admins si possible
        ):
            self._maybe_flush(request)

        return response

    def _maybe_flush(self, request) -> None:
        """
        Flush les événements session si le délai minimum est écoulé.
        """
        last_flush = request.session.get('_reco_last_flush', 0)
        now        = time.time()

        if now - last_flush >= self.FLUSH_INTERVAL_SECONDS:
            try:
                RecommendationService.flush_session_events(
                    request.user, request
                )
                request.session['_reco_last_flush'] = now
                request.session.modified = True
            except Exception as e:
                logger.warning(f"[Reco] Middleware flush échoué : {e}")
