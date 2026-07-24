class SharePayAPIError(Exception):
    def __init__(self, message: str, status_code: int = None, response: dict = None):
        self.status_code = status_code
        self.response = response
        super().__init__(message)

class InvalidWebhookSignatureError(Exception):
    pass

class DuplicatePaymentError(Exception):
    pass

class PaymentVerificationError(Exception):
    pass