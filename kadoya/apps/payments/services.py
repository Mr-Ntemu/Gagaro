import hashlib
import hmac
import requests
import logging
from django.conf import settings
from django.db import transaction as db_transaction
from django.db import models
from django.utils import timezone
from .models import PaymentAttempt
from .exceptions import (
    FlutterwaveAPIError, 
    PaymentVerificationError, 
    DuplicatePaymentError
)

logger = logging.getLogger('apps.payments')

class FlutterwaveService:
    """
    Client bas niveau pour l'API Flutterwave V3.
    """
    BASE_URL   = settings.FLW_BASE_URL
    SECRET_KEY = settings.FLW_SECRET_KEY

    @classmethod
    def _get_headers(cls) -> dict:
        return {
            'Authorization': f'Bearer {cls.SECRET_KEY}',
            'Content-Type':  'application/json',
        }

    @classmethod
    def initiate_mobile_money_charge(cls, payload: dict) -> dict:
        url = f"{cls.BASE_URL}/charges?type=mobile_money_franco"
        try:
            response = requests.post(
                url,
                json    = payload,
                headers = cls._get_headers(),
                timeout = 30,
            )
            data = response.json()

            if response.status_code not in [200, 201] or data.get('status') != 'success':
                raise FlutterwaveAPIError(
                    message     = data.get('message', 'Erreur API Flutterwave'),
                    status_code = response.status_code,
                    response    = data,
                )
            return data.get('data', {})

        except requests.exceptions.Timeout:
            raise FlutterwaveAPIError("Timeout : l'API Flutterwave ne répond pas.")
        except requests.exceptions.ConnectionError:
            raise FlutterwaveAPIError("Connexion impossible à l'API Flutterwave.")

    @classmethod
    def verify_transaction(cls, flw_transaction_id: str) -> dict:
        url = f"{cls.BASE_URL}/transactions/{flw_transaction_id}/verify"
        try:
            response = requests.get(
                url,
                headers = cls._get_headers(),
                timeout = 15,
            )
            data = response.json()

            if response.status_code != 200 or data.get('status') != 'success':
                raise PaymentVerificationError(
                    f"Vérification échouée pour transaction {flw_transaction_id}"
                )
            return data.get('data', {})

        except requests.exceptions.RequestException as e:
            raise PaymentVerificationError(f"Erreur réseau lors de la vérification : {e}")

    @staticmethod
    def verify_webhook_signature(request_body: bytes, received_hash: str) -> bool:
        expected_hash = settings.FLW_SECRET_HASH
        return hmac.compare_digest(received_hash, expected_hash)


class PaymentService:
    """
    Logique métier complète du paiement Kadoya.
    """

    @staticmethod
    def initiate_payment(
        order,
        phone_number: str,
        payment_method: str,
        user,
    ) -> PaymentAttempt:
        if order.status != 'pending':
            raise DuplicatePaymentError(
                f"La commande {order.reference} n'est pas en attente de paiement."
            )

        existing_success = order.payment_attempts.filter(status='success').first()
        if existing_success:
            raise DuplicatePaymentError(
                f"La commande {order.reference} est déjà payée."
            )

        # Nettoyer le numéro (Flutterwave attend 237XXXXXXXXX)
        clean_phone = phone_number.replace('+', '').replace(' ', '')
        if not clean_phone.startswith('237'):
            clean_phone = f"237{clean_phone}"

        payload = {
            'phone_number': clean_phone,
            'amount':       float(order.total_amount),
            'currency':     'XAF',
            'country':      'CM',
            'email':        user.email,
            'tx_ref':       order.reference,
            'fullname':     user.get_full_name(),
            'redirect_url': f"{settings.SITE_URL}/paiement/callback/",
        }

        flw_response = FlutterwaveService.initiate_mobile_money_charge(payload)

        attempt = PaymentAttempt.objects.create(
            order              = order,
            user               = user,
            flw_tx_ref         = order.reference,
            amount             = order.total_amount,
            currency           = 'XAF',
            payment_method     = payment_method,
            phone_number       = clean_phone,
            status             = PaymentAttempt.AttemptStatus.PENDING,
            flw_init_response  = flw_response,
        )
        return attempt

    @staticmethod
    @db_transaction.atomic
    def handle_successful_webhook(webhook_data: dict) -> None:
        data             = webhook_data.get('data', {})
        tx_ref           = data.get('tx_ref')
        flw_tx_id        = str(data.get('id', ''))
        
        try:
            attempt = PaymentAttempt.objects.select_related('order', 'user').get(
                flw_tx_ref=tx_ref
            )
        except PaymentAttempt.DoesNotExist:
            logger.warning(f"Webhook reçu pour tx_ref inconnu : {tx_ref}")
            return

        if attempt.status == PaymentAttempt.AttemptStatus.SUCCESS:
            return

        verified = FlutterwaveService.verify_transaction(flw_tx_id)

        # Vérification stricte
        if (float(verified.get('amount', 0)) < float(attempt.amount)
                or verified.get('currency') != attempt.currency):
            raise PaymentVerificationError(
                f"Montant ou devise invalide pour {tx_ref}."
            )

        now = timezone.now()

        attempt.status             = PaymentAttempt.AttemptStatus.SUCCESS
        attempt.flw_transaction_id = flw_tx_id
        attempt.flw_webhook_payload = webhook_data
        attempt.flw_verify_response = verified
        attempt.confirmed_at        = now
        attempt.save()

        order = attempt.order
        order.status            = 'paid'
        order.payment_method    = attempt.payment_method
        order.payment_reference = flw_tx_id
        order.paid_at           = now
        order.save(update_fields=[
            'status', 'payment_method', 'payment_reference', 'paid_at', 'updated_at'
        ])

        from apps.orders.models import OrderStatusHistory
        OrderStatusHistory.objects.create(
            order      = order,
            old_status = 'pending',
            new_status = 'paid',
            note       = f"Paiement confirmé via Flutterwave. TX ID : {flw_tx_id}",
        )

        PaymentService._decrement_stock(order)
        PaymentService._clear_user_cart(attempt.user)
        
        logger.info(f"Paiement réussi pour la commande {order.reference}")

    @staticmethod
    def _decrement_stock(order) -> None:
        from apps.catalogue.models import Product
        for item in order.items.all():
            updated = Product.objects.filter(
                pk=item.product_id,
                stock_quantity__gte=item.quantity
            ).update(
                stock_quantity=models.F('stock_quantity') - item.quantity
            )
            if not updated:
                logger.error(f"Stock insuffisant pour produit {item.product_id} (Commande {order.reference})")
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

    @staticmethod
    def handle_failed_webhook(webhook_data: dict) -> None:
        tx_ref = webhook_data.get('data', {}).get('tx_ref')
        try:
            attempt = PaymentAttempt.objects.get(flw_tx_ref=tx_ref)
            if attempt.status == PaymentAttempt.AttemptStatus.PENDING:
                attempt.status             = PaymentAttempt.AttemptStatus.FAILED
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
            'status':    latest.status,
            'message':   latest.get_status_display(),
            'order_status': order.status,
            'redirect_url': (
                f"/paiement/succes/{order.reference}/"
                if latest.is_successful else None
            ),
        }
