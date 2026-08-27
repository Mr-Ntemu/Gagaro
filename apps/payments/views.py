import json
import logging

from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from apps.orders.models import Order
from .models import PaymentAttempt
from .services import MonetbilService, PaymentService
from .exceptions import MonetbilAPIError, DuplicatePaymentError, PaymentVerificationError

logger = logging.getLogger('apps.payments')


class InitiatePaymentView(LoginRequiredMixin, View):
    template_name = 'payments/initiate.html'

    def get(self, request, reference: str):
        order = get_object_or_404(
            Order, reference=reference, user=request.user, status='pending'
        )
        return render(request, self.template_name, {
            'order': order,
            'payment_methods': [
                {
                    'id':     'MTN_MOMO_CM',
                    'label':  'MTN Mobile Money',
                    'logo':   'https://upload.wikimedia.org/wikipedia/commons/a/af/MTN_Logo.svg',
                    'prefix': '237 67X / 65X'
                },
                {
                    'id':     'ORANGE_MONEY_CM',
                    'label':  'Orange Money',
                    'logo':   'https://upload.wikimedia.org/wikipedia/commons/c/c8/Orange_logo.svg',
                    'prefix': '237 69X'
                },
            ]
        })

    def post(self, request, reference: str):
        order = get_object_or_404(
            Order, reference=reference, user=request.user, status='pending'
        )
        phone_number   = request.POST.get('phone_number', '').strip()
        payment_method = request.POST.get('payment_method', 'MTN_MOMO_CM')

        if not phone_number:
            messages.error(request, "Veuillez saisir votre numéro Mobile Money.")
            return redirect('payments:initiate', reference=reference)

        notify_url = request.build_absolute_uri(
            reverse('payments:monetbil_notify')
        )

        try:
            PaymentService.initiate_payment(
                order=order,
                phone_number=phone_number,
                payment_method=payment_method,
                user=request.user,
                notify_url=notify_url,
            )
            return redirect('payments:pending', reference=order.reference)

        except DuplicatePaymentError as e:
            messages.warning(request, str(e))
            return redirect('orders:confirmation', reference=reference)
        except MonetbilAPIError as e:
            logger.error(f"Erreur API Monetbil : {e}")
            messages.error(request, "Impossible d'initier le paiement. Réessayez.")
            return render(request, self.template_name, {
                'order': order,
                'error': str(e)
            })
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('payments:initiate', reference=reference)


class PaymentPendingView(LoginRequiredMixin, View):
    template_name = 'payments/pending.html'

    def get(self, request, reference: str):
        order = get_object_or_404(Order, reference=reference, user=request.user)
        return render(request, self.template_name, {
            'order':       order,
            'poll_url':    reverse('payments:status',  kwargs={'reference': reference}),
            'success_url': reverse('payments:success', kwargs={'reference': reference}),
            'failed_url':  reverse('payments:failed',  kwargs={'reference': reference}),
        })


class PaymentStatusView(LoginRequiredMixin, View):
    def get(self, request, reference: str):
        order  = get_object_or_404(Order, reference=reference, user=request.user)
        status = PaymentService.get_payment_status(order)
        return JsonResponse(status)


class MonetbilNotifyView(View):
    """Reçoit les notifications de paiement Monetbil (notify_url)."""

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            payload = request.POST.dict()

        payment_id = payload.get('paymentId', '')
        logger.info(f"Notification Monetbil reçue : paymentId={payment_id}")

        if not payment_id:
            return HttpResponse(status=400)

        try:
            # Vérifie le statut réel auprès de Monetbil
            verified = MonetbilService.check_payment(payment_id)
            transaction = verified.get('transaction')
            if transaction:
                tx_status = int(transaction.get('status', 0))
                if tx_status == 1:
                    PaymentService.handle_successful_payment(payment_id, payload)
                elif tx_status in (0, -1, -2):
                    PaymentService.handle_failed_payment(payment_id, payload)
        except PaymentVerificationError as e:
            logger.error(f"Erreur vérification paiement : {e}")
        except Exception as e:
            logger.exception(f"Erreur inattendue dans la notification : {e}")

        return HttpResponse(status=200)


class PaymentSuccessView(LoginRequiredMixin, DetailView):
    template_name       = 'payments/success.html'
    context_object_name = 'order'

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)

    def get_object(self):
        return get_object_or_404(
            self.get_queryset(),
            reference=self.kwargs['reference'],
            status__in=['paid', 'pending']
        )


class PaymentFailedView(LoginRequiredMixin, View):
    template_name = 'payments/failed.html'

    def get(self, request, reference: str):
        order = get_object_or_404(Order, reference=reference, user=request.user)
        return render(request, self.template_name, {'order': order})
