from django.contrib import admin
from apps.reviews.models import Review, ReviewPhoto
from apps.reviews.services import ReviewService

class ReviewPhotoInline(admin.TabularInline):
    model         = ReviewPhoto
    extra         = 0
    readonly_fields = ['thumbnail_preview', 'created_at']
    fields        = ['image', 'thumbnail_preview', 'caption', 'order']

    def thumbnail_preview(self, obj):
        from django.utils.html import format_html
        if obj.thumbnail:
            return format_html('<img src="{}" width="100" height="100" style="object-fit:cover;border-radius:8px;" />', obj.thumbnail.url)
        return "Pas de miniature"
    thumbnail_preview.short_description = "Aperçu"

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display    = ['__str__', 'rating', 'status',
                        'has_photos', 'created_at', 'moderated_at']
    list_filter     = ['status', 'rating', 'created_at']
    search_fields   = ['user__email', 'product__title', 'body']
    readonly_fields = ['user', 'product', 'order', 'order_item',
                        'helpful_count', 'created_at', 'updated_at',
                        'moderated_by', 'moderated_at']
    inlines         = [ReviewPhotoInline]
    list_editable   = ['status']
    actions         = ['approve_selected', 'reject_selected']

    def approve_selected(self, request, queryset):
        count = 0
        for review in queryset.filter(status='pending'):
            ReviewService.approve_review(review.pk, request.user)
            count += 1
        self.message_user(request, f"{count} avis approuvés.")
    approve_selected.short_description = "Approuver les avis sélectionnés"

    def reject_selected(self, request, queryset):
        count = queryset.filter(status='pending').update(
            status='rejected',
            moderated_by=request.user,
        )
        self.message_user(request, f"{count} avis rejetés.")
    reject_selected.short_description = "Rejeter les avis sélectionnés"
