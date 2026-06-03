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
from .services import FlutterwaveService, PaymentService
from .exceptions import FlutterwaveAPIError, DuplicatePaymentError, PaymentVerificationError

logger = logging.getLogger('apps.payments')

class InitiatePaymentView(LoginRequiredMixin, View):
    template_name = 'payments/initiate.html'

    def get(self, request, reference: str):
        order = get_object_or_404(
            Order, reference=reference, user=request.user, status='pending'
        )
        return render(request, self.template_name, {
            'order':        order,
            'flw_pub_key':  settings.FLW_PUBLIC_KEY,
            'payment_methods': [
                {'id': 'mtn',    'label': 'MTN Mobile Money',
                 'logo': 'https://upload.wikimedia.org/wikipedia/commons/a/af/MTN_Logo.svg', 'prefix': '237 67X / 65X'},
                {'id': 'orange', 'label': 'Orange Money',
                 'logo': 'https://upload.wikimedia.org/wikipedia/commons/c/c8/Orange_logo.svg', 'prefix': '237 69X'},
            ]
        })

    def post(self, request, reference: str):
        order = get_object_or_404(
            Order, reference=reference, user=request.user, status='pending'
        )
        phone_number    = request.POST.get('phone_number', '').strip()
        payment_method  = request.POST.get('payment_method', 'mtn')

        if not phone_number:
            messages.error(request, "Veuillez saisir votre numéro Mobile Money.")
            return redirect('payments:initiate', reference=reference)

        try:
            attempt = PaymentService.initiate_payment(
                order          = order,
                phone_number   = phone_number,
                payment_method = payment_method,
                user           = request.user,
            )
            return redirect('payments:pending', reference=order.reference)

        except DuplicatePaymentError as e:
            messages.warning(request, str(e))
            return redirect('orders:confirmation', reference=reference)

        except FlutterwaveAPIError as e:
            logger.error(f"Erreur API Flutterwave: {e}")
            messages.error(
                request,
                "Impossible d'initier le paiement pour l'instant. Réessayez dans quelques minutes."
            )
            return render(request, self.template_name, {
                'order': order, 'error': str(e)
            })


class PaymentPendingView(LoginRequiredMixin, View):
    template_name = 'payments/pending.html'

    def get(self, request, reference: str):
        order = get_object_or_404(Order, reference=reference, user=request.user)
        return render(request, self.template_name, {
            'order':       order,
            'poll_url':    reverse('payments:status', kwargs={'reference': reference}),
            'success_url': reverse('payments:success', kwargs={'reference': reference}),
            'failed_url':  reverse('payments:failed',  kwargs={'reference': reference}),
        })


class PaymentStatusView(LoginRequiredMixin, View):
    def get(self, request, reference: str):
        order  = get_object_or_404(Order, reference=reference, user=request.user)
        status = PaymentService.get_payment_status(order)
        return JsonResponse(status)


class FlutterwaveWebhookView(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        received_hash = request.headers.get('verif-hash', '')
        if not FlutterwaveService.verify_webhook_signature(
            request.body, received_hash
        ):
            logger.warning(f"Webhook Flutterwave rejeté — signature invalide. IP: {request.META.get('REMOTE_ADDR')}")
            return HttpResponse(status=401)

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponse(status=400)

        logger.info(
            f"Webhook Flutterwave reçu : type={payload.get('event')}, "
            f"tx_ref={payload.get('data', {}).get('tx_ref')}, status={payload.get('data', {}).get('status')}"
        )

        try:
            event_type = payload.get('event', '')
            status     = payload.get('data', {}).get('status', '')

            if event_type == 'charge.completed' and status == 'successful':
                PaymentService.handle_successful_webhook(payload)
            elif status in ['failed', 'cancelled']:
                PaymentService.handle_failed_webhook(payload)

        except PaymentVerificationError as e:
            logger.error(f"Erreur de vérification paiement : {e}")
        except Exception as e:
            logger.exception(f"Erreur inattendue dans le webhook : {e}")

        return HttpResponse(status=200)


class PaymentCallbackView(LoginRequiredMixin, View):
    def get(self, request):
        status = request.GET.get('status', '')
        tx_ref = request.GET.get('tx_ref', '')

        if not tx_ref:
            return redirect('orders:cart')

        try:
            order = Order.objects.get(reference=tx_ref, user=request.user)
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
            status='paid'
        )


class PaymentFailedView(LoginRequiredMixin, View):
    template_name = 'payments/failed.html'

    def get(self, request, reference: str):
        order = get_object_or_404(Order, reference=reference, user=request.user)
        return render(request, self.template_name, {'order': order})
