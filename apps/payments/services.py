import hmac
import hashlib
import re
import logging
import requests as http_requests
from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone
from .models import PaymentAttempt
from .exceptions import (
    SharePayAPIError,
    PaymentVerificationError,
    DuplicatePaymentError,
)

logger = logging.getLogger('apps.payments')


class SharePayService:
    """Client bas niveau pour l'API SharePay."""

    BASE_URL   = settings.SHAREPAY_BASE_URL
    API_KEY    = settings.SHAREPAY_API_KEY

    @classmethod
    def _get_headers(cls) -> dict:
        return {
            'Content-Type': 'application/json',
            'X-API-KEY': cls.API_KEY,
        }

    @classmethod
    def create_checkout(cls, order, user) -> dict:
        """
        Checkout : génère un lien de paiement SharePay.
        L'utilisateur choisit son opérateur sur la page hébergée.
        """
        try:
            response = http_requests.post(
                f"{cls.BASE_URL}/api/v1/pay-in/checkout",
                json={
                    'amount':            int(order.total_amount),
                    'currency':          'XAF',
                    'merchantReference': order.reference,
                    'description':       f"Commande Gagaro #{order.reference}",
                    'successUrl': f"{settings.SITE_URL}/paiement/succes/{order.reference}/",
                    'cancelUrl':  f"{settings.SITE_URL}/paiement/echec/{order.reference}/",
                },
                headers=cls._get_headers(),
                timeout=30,
            )
            data = response.json()
            if not data.get('success'):
                raise SharePayAPIError(
                    message=data.get('message', 'Erreur SharePay'),
                    status_code=response.status_code,
                    response=data,
                )
            return data['data']  # {reference, status, paymentUrl}

        except http_requests.exceptions.Timeout:
            raise SharePayAPIError("Timeout : SharePay ne répond pas.")
        except http_requests.exceptions.ConnectionError:
            raise SharePayAPIError("Connexion impossible à SharePay.")

    @classmethod
    def create_charge(cls, phone: str, payment_method: str, order, user) -> dict:
        """
        Charge directe : débit Mobile Money sans page intermédiaire.
        """
        try:
            response = http_requests.post(
                f"{cls.BASE_URL}/api/v1/pay-in/charge",
                json={
                    'amount':           int(order.total_amount),
                    'currency':         'XAF',
                    'paymentMethod':    payment_method,  # MTN_MOMO_CM ou ORANGE_MONEY_CM
                    'payerAccount':     phone,
                    'payerName':        user.get_full_name(),
                    'payerEmail':       user.email,
                    'merchantReference': order.reference,
                    'description':      f"Commande Gagaro #{order.reference}",
                    'idempotencyKey':   f"idem-{order.reference}-v1",
                },
                headers=cls._get_headers(),
                timeout=30,
            )
            data = response.json()
            if not data.get('success'):
                raise SharePayAPIError(
                    message=data.get('message', 'Erreur SharePay'),
                    status_code=response.status_code,
                    response=data,
                )
            return data['data']  # {reference, status, paymentMethod, ...}

        except http_requests.exceptions.Timeout:
            raise SharePayAPIError("Timeout : SharePay ne répond pas.")
        except http_requests.exceptions.ConnectionError:
            raise SharePayAPIError("Connexion impossible à SharePay.")

    @classmethod
    def check_status(cls, sharepay_reference: str) -> dict:
        """Vérifier le statut d'un paiement auprès de SharePay."""
        response = http_requests.get(
            f"{cls.BASE_URL}/api/v1/pay-in/check_status/{sharepay_reference}",
            headers=cls._get_headers(),
            timeout=15,
        )
        data = response.json()
        if not data.get('success'):
            raise SharePayAPIError(data.get('message', 'Erreur vérification'))
        return data['data']  # {reference, status, amount, currency, ...}

    @classmethod
    def verify_webhook_signature(cls, request_body: bytes, received_sig: str) -> bool:
        """Vérifie la signature HMAC-SHA256 du webhook SharePay."""
        expected = hmac.new(
            settings.SHAREPAY_WEBHOOK_SECRET.encode(),
            request_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(received_sig, expected)


class PaymentService:
    """Logique métier complète du paiement Gagaro."""

    @staticmethod
    def _clean_phone(phone_number: str) -> str:
        """Normalise le numéro au format 237XXXXXXXXX."""
        clean = re.sub(r'[\s\+\-\(\)]', '', phone_number)
        clean = re.sub(r'^(00237|237)', '', clean)
        clean = f"237{clean}"
        if len(clean) != 12:
            raise ValueError(f"Numéro invalide : {phone_number}")
        return clean

    @staticmethod
    def initiate_checkout(order, user) -> tuple:
        """
        Mode Checkout : redirige vers la page SharePay.
        Retourne (attempt, payment_url).
        """
        if order.status != 'pending':
            raise DuplicatePaymentError(
                f"La commande {order.reference} n'est pas en attente."
            )
        if order.payment_attempts.filter(status='success').exists():
            raise DuplicatePaymentError(
                f"La commande {order.reference} est déjà payée."
            )

        sp_data = SharePayService.create_checkout(order, user)

        attempt = PaymentAttempt.objects.create(
            order              = order,
            user               = user,
            flw_tx_ref         = sp_data['reference'],   # référence SharePay
            amount             = order.total_amount,
            currency           = 'XAF',
            payment_method     = 'checkout',
            status             = PaymentAttempt.AttemptStatus.PENDING,
            flw_init_response  = sp_data,
        )
        return attempt, sp_data['paymentUrl']

    @staticmethod
    def initiate_charge(order, phone_number: str, payment_method: str, user) -> PaymentAttempt:
        """
        Mode Charge directe : débit Mobile Money immédiat.
        payment_method : 'MTN_MOMO_CM' ou 'ORANGE_MONEY_CM'
        """
        if order.status != 'pending':
            raise DuplicatePaymentError(
                f"La commande {order.reference} n'est pas en attente."
            )
        if order.payment_attempts.filter(status='success').exists():
            raise DuplicatePaymentError(
                f"La commande {order.reference} est déjà payée."
            )

        clean_phone = PaymentService._clean_phone(phone_number)
        sp_data     = SharePayService.create_charge(
            phone=clean_phone,
            payment_method=payment_method,
            order=order,
            user=user,
        )

        attempt = PaymentAttempt.objects.create(
            order              = order,
            user               = user,
            flw_tx_ref         = sp_data['reference'],
            amount             = order.total_amount,
            currency           = 'XAF',
            payment_method     = payment_method,
            phone_number       = clean_phone,
            status             = PaymentAttempt.AttemptStatus.PENDING,
            flw_init_response  = sp_data,
        )
        return attempt

    @staticmethod
    @db_transaction.atomic
    def handle_successful_webhook(webhook_data: dict) -> None:
        """Traite un webhook payment.success de SharePay."""
        data      = webhook_data.get('data', {})
        sp_ref    = data.get('reference', '')
        event     = webhook_data.get('event', '')

        try:
            attempt = PaymentAttempt.objects.select_related(
                'order', 'user'
            ).get(flw_tx_ref=sp_ref)
        except PaymentAttempt.DoesNotExist:
            logger.warning(f"Webhook reçu pour référence inconnue : {sp_ref}")
            return

        # Idempotence
        if attempt.status == PaymentAttempt.AttemptStatus.SUCCESS:
            return

        # Vérification stricte côté SharePay
        verified = SharePayService.check_status(sp_ref)
        if verified.get('status') != 'SUCCESS':
            raise PaymentVerificationError(
                f"Statut SharePay invalide pour {sp_ref} : {verified.get('status')}"
            )
        if int(verified.get('amount', 0)) != int(attempt.amount):
            raise PaymentVerificationError(
                f"Montant invalide pour {sp_ref}."
            )

        now = timezone.now()
        attempt.status              = PaymentAttempt.AttemptStatus.SUCCESS
        attempt.flw_transaction_id  = sp_ref
        attempt.flw_webhook_payload = webhook_data
        attempt.flw_verify_response = verified
        attempt.confirmed_at        = now
        attempt.save()

        order = attempt.order
        order.status            = 'paid'
        order.payment_method    = attempt.payment_method
        order.payment_reference = sp_ref
        order.paid_at           = now
        order.save(update_fields=[
            'status', 'payment_method', 'payment_reference', 'paid_at', 'updated_at'
        ])

        from apps.orders.models import OrderStatusHistory
        OrderStatusHistory.objects.create(
            order      = order,
            old_status = 'pending',
            new_status = 'paid',
            note       = f"Paiement confirmé via SharePay. Réf : {sp_ref}",
        )

        PaymentService._decrement_stock(order)
        PaymentService._clear_user_cart(attempt.user)
        logger.info(f"Paiement réussi pour la commande {order.reference}")

    @staticmethod
    def handle_failed_webhook(webhook_data: dict) -> None:
        """Traite un webhook payment.failed ou payment.cancelled."""
        sp_ref = webhook_data.get('data', {}).get('reference', '')
        try:
            attempt = PaymentAttempt.objects.get(flw_tx_ref=sp_ref)
            if attempt.status == PaymentAttempt.AttemptStatus.PENDING:
                attempt.status              = PaymentAttempt.AttemptStatus.FAILED
                attempt.flw_webhook_payload = webhook_data
                attempt.save(update_fields=['status', 'flw_webhook_payload'])
        except PaymentAttempt.DoesNotExist:
            pass

    @staticmethod
    def get_payment_status(order) -> dict:
        latest = order.payment_attempts.order_by('-initiated_at').first()
        if not latest:
            return {'status': 'none', 'message': 'Aucun paiement initié'}
        return {
            'status':       latest.status,
            'message':      latest.get_status_display(),
            'order_status': order.status,
            'redirect_url': (
                f"/paiement/succes/{order.reference}/"
                if latest.is_successful else None
            ),
        }

    @staticmethod
    def _decrement_stock(order) -> None:
        from apps.catalogue.models import Product
        from django.db import models
        for item in order.items.all():
            updated = Product.objects.filter(
                pk=item.product_id,
                stock_quantity__gte=item.quantity
            ).update(
                stock_quantity=models.F('stock_quantity') - item.quantity
            )
            if not updated:
                logger.error(
                    f"Stock insuffisant pour produit {item.product_id} "
                    f"(Commande {order.reference})"
                )
                Product.objects.filter(pk=item.product_id).update(
                    stock_quantity=0, status='sold_out'
                )

    @staticmethod
    def _clear_user_cart(user) -> None:
        from apps.orders.models import Cart
        try:
            cart = Cart.objects.get(user=user)
            cart.items.all().delete()
        except Cart.DoesNotExist:
            pass