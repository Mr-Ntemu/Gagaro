from django.contrib import admin
from django.utils import timezone
from .models import ArtisanProfile, WithdrawalRequest


@admin.register(ArtisanProfile)
class ArtisanProfileAdmin(admin.ModelAdmin):
    list_display    = ['shop_name', 'user', 'city', 'is_verified',
                        'total_revenue', 'total_payout', 'created_at']
    list_filter     = ['is_verified', 'city', 'payout_operator']
    search_fields   = ['shop_name', 'user__email', 'user__first_name']
    readonly_fields = ['total_sales_count', 'total_revenue',
                        'total_commission', 'total_payout',
                        'verified_at', 'created_at', 'updated_at']
    list_editable   = ['is_verified']

    actions = ['verify_artisans']

    def verify_artisans(self, request, queryset):
        """Action admin : vérifier les artisans sélectionnés."""
        now = timezone.now()
        queryset.update(is_verified=True, verified_at=now)
        self.message_user(
            request,
            f"{queryset.count()} artisan(s) vérifiés."
        )
    verify_artisans.short_description = "Vérifier les artisans sélectionnés"


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display    = ['artisan', 'amount', 'operator', 'status',
                        'created_at', 'processed_at']
    list_filter     = ['status', 'operator']
    list_editable   = ['status']
    readonly_fields = ['created_at', 'updated_at']
    search_fields   = ['artisan__shop_name', 'artisan__user__email']
