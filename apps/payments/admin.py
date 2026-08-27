from django.contrib import admin
from .models import PaymentAttempt
from .services import MonetbilService, PaymentService
from .exceptions import PaymentVerificationError

@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    list_display    = ['mb_payment_id', 'order', 'user', 'amount',
                        'payment_method', 'status', 'initiated_at', 'confirmed_at']
    list_filter     = ['status', 'payment_method', 'currency']
    search_fields   = ['mb_payment_id', 'mb_transaction_id', 'order__reference',
                        'user__email', 'phone_number']
    readonly_fields = ['mb_payment_id', 'mb_transaction_id',
                        'amount', 'currency', 'mb_init_response',
                        'mb_webhook_payload', 'mb_verify_response',
                        'initiated_at', 'confirmed_at']
    ordering        = ['-initiated_at']

    actions = ['reverify_transaction']

    def reverify_transaction(self, request, queryset):
        for attempt in queryset.filter(status__in=['pending', 'processing']):
            try:
                verified = MonetbilService.check_payment(attempt.mb_payment_id)
                transaction = verified.get('transaction')
                if transaction and int(transaction.get('status', 0)) == 1:
                    PaymentService.handle_successful_payment(
                        attempt.mb_payment_id, verified
                    )
                    self.message_user(request, f"Transaction {attempt.mb_payment_id} confirmée manuellement.")
            except Exception as e:
                self.message_user(request, f"Erreur pour {attempt.mb_payment_id} : {e}", level='ERROR')

    reverify_transaction.short_description = "Re-vérifier les transactions sélectionnées"
