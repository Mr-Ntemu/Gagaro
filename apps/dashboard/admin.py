from django.contrib import admin
from apps.dashboard.models import PromoCode, InternalNotification, ReviewReport

@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display     = ['code', 'occasion', 'discount_type', 'discount_value',
                         'current_uses', 'max_uses', 'valid_until', 'is_active']
    list_filter      = ['is_active', 'discount_type', 'occasion']
    search_fields    = ['code', 'description']
    list_editable    = ['is_active']
    readonly_fields  = ['current_uses', 'created_at', 'updated_at']
    filter_horizontal = ['applicable_categories']


@admin.register(InternalNotification)
class InternalNotificationAdmin(admin.ModelAdmin):
    list_display  = ['title', 'type', 'priority', 'is_read', 'created_at']
    list_filter   = ['type', 'priority', 'is_read']
    readonly_fields = ['created_at', 'read_at', 'read_by']


@admin.register(ReviewReport)
class ReviewReportAdmin(admin.ModelAdmin):
    list_display  = ['review_id', 'reported_by', 'reason', 'status', 'created_at']
    list_filter   = ['status', 'reason']
    list_editable = ['status']
