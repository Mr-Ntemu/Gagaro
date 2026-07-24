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
from .services import SharePayService, PaymentService
from .exceptions import SharePayAPIError, DuplicatePaymentError, PaymentVerificationError

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
        payment_mode   = request.POST.get('payment_mode', 'checkout')
        phone_number   = request.POST.get('phone_number', '').strip()
        payment_method = request.POST.get('payment_method', 'MTN_MOMO_CM')

        try:
            if payment_mode == 'checkout':
                attempt, payment_url = PaymentService.initiate_checkout(
                    order, request.user
                )
                return redirect(payment_url)
            else:
                if not phone_number:
                    messages.error(
                        request, "Veuillez saisir votre numéro Mobile Money."
                    )
                    return redirect('payments:initiate', reference=reference)
                PaymentService.initiate_charge(
                    order=order,
                    phone_number=phone_number,
                    payment_method=payment_method,
                    user=request.user,
                )
                return redirect('payments:pending', reference=order.reference)

        except DuplicatePaymentError as e:
            messages.warning(request, str(e))
            return redirect('orders:confirmation', reference=reference)
        except SharePayAPIError as e:
            logger.error(f"Erreur API SharePay : {e}")
            messages.error(request, "Impossible d'initier le paiement. Réessayez.")
            return render(request, self.template_name, {
                'order': order,
                'error': str(e)
            })


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


class SharePayWebhookView(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        received_sig = request.headers.get('X-Sharepay-Signature', '')
        if not SharePayService.verify_webhook_signature(request.body, received_sig):
            logger.warning(
                f"Webhook SharePay rejeté — signature invalide. "
                f"IP: {request.META.get('REMOTE_ADDR')}"
            )
            return HttpResponse(status=401)

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponse(status=400)

        event = payload.get('event', '')
        logger.info(f"Webhook SharePay reçu : event={event}")

        try:
            if event == 'payment.success':
                PaymentService.handle_successful_webhook(payload)
            elif event in ['payment.failed', 'payment.cancelled']:
                PaymentService.handle_failed_webhook(payload)
            elif event == 'webhook.test':
                logger.info("Webhook test SharePay reçu — OK")

        except PaymentVerificationError as e:
            logger.error(f"Erreur vérification paiement : {e}")
        except Exception as e:
            logger.exception(f"Erreur inattendue dans le webhook : {e}")

        return HttpResponse(status=200)


class PaymentCallbackView(View):
    def get(self, request):
        status = request.GET.get('status', '')
        tx_ref = request.GET.get('tx_ref', '')

        if not tx_ref:
            return redirect('orders:cart')

        try:
            order = Order.objects.get(reference=tx_ref)
        except Order.DoesNotExist:
            return redirect('core:home')

        if status == 'successful' or order.status == 'paid':
            return redirect('payments:success', reference=order.reference)
        else:
            messages.warning(request, "Paiement non finalisé.")
            return redirect('payments:failed', reference=order.reference)


class PaymentSuccessView(LoginRequiredMixin, DetailView):
    template_name       = 'payments/success.html'
    context_object_name = 'order'

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)

    def get_object(self):
        return get_object_or_404(
            self.get_queryset(),
            reference=self.kwargs['reference'],
            status__in=['paid', 'pending']  # ← corrigé aussi
        )


class PaymentFailedView(LoginRequiredMixin, View):
    template_name = 'payments/failed.html'

    def get(self, request, reference: str):
        order = get_object_or_404(Order, reference=reference, user=request.user)
        return render(request, self.template_name, {'order': order})