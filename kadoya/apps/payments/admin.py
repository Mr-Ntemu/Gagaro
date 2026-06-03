from django.contrib import admin
from .models import PaymentAttempt
from .services import FlutterwaveService, PaymentService
from .exceptions import PaymentVerificationError

@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    list_display    = ['flw_tx_ref', 'order', 'user', 'amount',
                        'payment_method', 'status', 'initiated_at', 'confirmed_at']
    list_filter     = ['status', 'payment_method', 'currency']
    search_fields   = ['flw_tx_ref', 'flw_transaction_id', 'order__reference',
                        'user__email', 'phone_number']
    readonly_fields = ['flw_tx_ref', 'flw_transaction_id', 'flw_ref',
                        'amount', 'currency', 'flw_init_response',
                        'flw_webhook_payload', 'flw_verify_response',
                        'initiated_at', 'confirmed_at']
    ordering        = ['-initiated_at']

    actions = ['reverify_transaction']

    def reverify_transaction(self, request, queryset):
        for attempt in queryset.filter(status='pending', flw_transaction_id__gt=''):
            try:
                verified = FlutterwaveService.verify_transaction(attempt.flw_transaction_id)
                if verified.get('status') == 'successful':
                    fake_payload = {'data': {
                        'tx_ref': attempt.flw_tx_ref,
                        'id': attempt.flw_transaction_id,
                        'amount': float(attempt.amount),
                        'currency': attempt.currency,
                        'status': 'successful',
                    }, 'event': 'charge.completed'}
                    PaymentService.handle_successful_webhook(fake_payload)
                    self.message_user(request, f"Transaction {attempt.flw_tx_ref} confirmée manuellement.")
            except Exception as e:
                self.message_user(request, f"Erreur pour {attempt.flw_tx_ref} : {e}", level='ERROR')

    reverify_transaction.short_description = "Re-vérifier les transactions sélectionnées"
