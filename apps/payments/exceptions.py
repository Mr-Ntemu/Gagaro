class FlutterwaveAPIError(Exception):
    """Erreur lors de l'appel à l'API Flutterwave."""
    def __init__(self, message: str, status_code: int = None, response: dict = None):
        self.status_code = status_code
        self.response    = response
        super().__init__(message)


class InvalidWebhookSignatureError(Exception):
    """Signature webhook invalide — requête non authentifiée."""
    pass


class DuplicatePaymentError(Exception):
    """Paiement déjà traité pour cette commande — protection idempotence."""
    pass


class PaymentVerificationError(Exception):
    """La vérification de transaction auprès de Flutterwave a échoué."""
    pass
