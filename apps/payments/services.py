import re
import logging
import requests as http_requests
from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone
from .models import PaymentAttempt
from .exceptions import (
    MonetbilAPIError,
    PaymentVerificationError,
    DuplicatePaymentError,
)

logger = logging.getLogger('apps.payments')


class MonetbilService:
    """Client bas niveau pour l'API Monetbil (Mobile Money)."""

    BASE_URL = settings.MONETBIL_API_URL
    SERVICE_KEY = settings.MONETBIL_SERVICE_KEY

    # Opérateurs Cameroun
    OPERATORS = {
        'MTN_MOMO_CM': 'CM_MTNMOBILEMONEY',
        'ORANGE_MONEY_CM': 'CM_ORANGEMONEY',
    }

    @classmethod
    def place_payment(cls, phone: str, amount: int, operator: str,
                      order, user, notify_url: str) -> dict:
        """
        Initie une demande de paiement Mobile Money.
        Retourne {paymentId, status, message, channel, ...}.
        """
        payload = {
            'service':      cls.SERVICE_KEY,
            'phonenumber':  phone,
            'amount':       str(amount),
            'operator':     operator,
            'currency':     'XAF',
            'country':      'CM',
            'payment_ref':  order.reference,
            'item_ref':     order.reference,
            'user':         user.email,
            'first_name':   user.first_name or '',
            'last_name':    user.last_name or '',
            'email':        user.email,
            'notify_url':   notify_url,
        }
        try:
            response = http_requests.post(
                f"{cls.BASE_URL}placePayment",
                json=payload,
                timeout=30,
            )
            try:
                data = response.json()
            except ValueError as exc:
                raise MonetbilAPIError(
                    "Réponse invalide reçue de Monetbil.",
                    status_code=response.status_code,
                ) from exc
            if data.get('status') != 'REQUEST_ACCEPTED':
                raise MonetbilAPIError(
                    message=data.get('message', 'Erreur Monetbil'),
                    status_code=response.status_code,
                    response=data,
                )
            return data  # {status, message, channel, paymentId, ...}

        except http_requests.exceptions.Timeout:
            raise MonetbilAPIError("Timeout : Monetbil ne répond pas.")
        except http_requests.exceptions.ConnectionError:
            raise MonetbilAPIError("Connexion impossible à Monetbil.")

    @classmethod
    def check_payment(cls, payment_id: str) -> dict:
        """Vérifie le statut d'un paiement auprès de Monetbil."""
        try:
            response = http_requests.post(
                f"{cls.BASE_URL}checkPayment",
                data={'paymentId': payment_id},
                timeout=15,
            )
            try:
                return response.json()  # {paymentId, message, transaction?}
            except ValueError as exc:
                raise MonetbilAPIError(
                    "Réponse invalide reçue de Monetbil.",
                    status_code=response.status_code,
                ) from exc

        except http_requests.exceptions.Timeout:
            raise MonetbilAPIError("Timeout : Monetbil ne répond pas.")
        except http_requests.exceptions.ConnectionError:
            raise MonetbilAPIError("Connexion impossible à Monetbil.")


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
    def initiate_payment(order, phone_number: str, payment_method: str,
                         user, notify_url: str) -> PaymentAttempt:
        """
        Initie un paiement Mobile Money via Monetbil.
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
        operator = MonetbilService.OPERATORS.get(
            payment_method, 'CM_MTNMOBILEMONEY'
        )

        mb_data = MonetbilService.place_payment(
            phone=clean_phone,
            amount=int(order.total_amount),
            operator=operator,
            order=order,
            user=user,
            notify_url=notify_url,
        )

        payment_id = mb_data.get('paymentId')
        if not payment_id:
            raise MonetbilAPIError(
                "Monetbil n’a pas retourné d’identifiant de paiement."
            )

        attempt = PaymentAttempt.objects.create(
            order            = order,
            user             = user,
            mb_payment_id    = str(payment_id),
            amount           = order.total_amount,
            currency         = 'XAF',
            payment_method   = payment_method,
            phone_number     = clean_phone,
            status           = PaymentAttempt.AttemptStatus.PROCESSING,
            mb_init_response = mb_data,
        )
        return attempt

    @staticmethod
    @db_transaction.atomic
    def handle_successful_payment(payment_id: str, webhook_data: dict = None) -> None:
        """Confirme un paiement réussi (via webhook ou polling)."""
        try:
            attempt = PaymentAttempt.objects.select_related(
                'order', 'user'
            ).get(mb_payment_id=payment_id)
        except PaymentAttempt.DoesNotExist:
            logger.warning(f"Paiement reçu pour ID inconnu : {payment_id}")
            return

        # Idempotence
        if attempt.status == PaymentAttempt.AttemptStatus.SUCCESS:
            return

        # Vérification stricte côté Monetbil
        verified = MonetbilService.check_payment(payment_id)
        transaction = verified.get('transaction')
        if not transaction:
            raise PaymentVerificationError(
                f"Transaction absente pour {payment_id}."
            )
        if int(transaction.get('status', 0)) != 1:
            raise PaymentVerificationError(
                f"Statut Monetbil invalide pour {payment_id} : "
                f"{transaction.get('status')}"
            )
        if int(transaction.get('amount', 0)) != int(attempt.amount):
            raise PaymentVerificationError(
                f"Montant invalide pour {payment_id}."
            )

        now = timezone.now()
        attempt.status              = PaymentAttempt.AttemptStatus.SUCCESS
        attempt.mb_transaction_id   = str(transaction.get('transaction_UUID', ''))
        attempt.mb_webhook_payload  = webhook_data
        attempt.mb_verify_response  = verified
        attempt.confirmed_at        = now
        attempt.save()

        order = attempt.order
        order.status            = 'paid'
        order.payment_method    = attempt.payment_method
        order.payment_reference = payment_id
        order.paid_at           = now
        order.save(update_fields=[
            'status', 'payment_method', 'payment_reference', 'paid_at', 'updated_at'
        ])

        from apps.orders.models import OrderStatusHistory
        OrderStatusHistory.objects.create(
            order      = order,
            old_status = 'pending',
            new_status = 'paid',
            note       = f"Paiement confirmé via Monetbil. ID : {payment_id}",
        )

        PaymentService._decrement_stock(order)
        PaymentService._clear_user_cart(attempt.user)
        logger.info(f"Paiement réussi pour la commande {order.reference}")

    @staticmethod
    def handle_failed_payment(payment_id: str, webhook_data: dict = None) -> None:
        """Marque un paiement comme échoué/annulé."""
        try:
            attempt = PaymentAttempt.objects.get(mb_payment_id=payment_id)
            if attempt.status in [
                PaymentAttempt.AttemptStatus.PENDING,
                PaymentAttempt.AttemptStatus.PROCESSING,
            ]:
                attempt.status             = PaymentAttempt.AttemptStatus.FAILED
                attempt.mb_webhook_payload = webhook_data
                attempt.save(update_fields=['status', 'mb_webhook_payload'])
        except PaymentAttempt.DoesNotExist:
            pass

    @staticmethod
    def get_payment_status(order) -> dict:
        latest = order.payment_attempts.order_by('-initiated_at').first()
        if not latest:
            return {'status': 'none', 'message': 'Aucun paiement initié'}

        # Si pas encore confirmé, interroge Monetbil en direct
        if latest.status in [
            PaymentAttempt.AttemptStatus.PROCESSING,
            PaymentAttempt.AttemptStatus.PENDING,
        ]:
            try:
                verified = MonetbilService.check_payment(latest.mb_payment_id)
                transaction = verified.get('transaction')
                if transaction:
                    tx_status = int(transaction.get('status', 0))
                    if tx_status == 1:
                        PaymentService.handle_successful_payment(
                            latest.mb_payment_id, verified
                        )
                    elif tx_status in (0, -1, -2):
                        PaymentService.handle_failed_payment(
                            latest.mb_payment_id, verified
                        )
            except Exception as e:
                logger.warning(f"Polling Monetbil échoué : {e}")

        latest.refresh_from_db()
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
