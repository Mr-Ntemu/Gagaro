from django.contrib import admin
from .models import BehaviorEvent, ClientProfile, RecommendationCache

@admin.register(BehaviorEvent)
class BehaviorEventAdmin(admin.ModelAdmin):
    list_display    = ['user', 'product', 'event_type',
                        'weight', 'occurred_at']
    list_filter     = ['event_type']
    search_fields   = ['user__email', 'product__title']
    readonly_fields = ['occurred_at', 'category_id', 'tags_snapshot']
    date_hierarchy  = 'occurred_at'

    def weight(self, obj):
        return BehaviorEvent.EVENT_WEIGHTS.get(obj.event_type, 0)
    weight.short_description = 'Poids'


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display    = ['user', 'events_count', 'last_rebuilt_at',
                        'top_categories_display']
    readonly_fields = ['favorite_categories', 'favorite_tags',
                        'avg_price_viewed', 'avg_price_purchased',
                        'last_rebuilt_at', 'events_count']
    search_fields   = ['user__email']

    def top_categories_display(self, obj):
        return ', '.join(str(c) for c in obj.top_categories[:3])
    top_categories_display.short_description = 'Top catégories'

    actions = ['rebuild_selected_profiles']

    def rebuild_selected_profiles(self, request, queryset):
        from .engine import RecommendationEngine
        count = 0
        for profile in queryset.select_related('user'):
            try:
                engine = RecommendationEngine(profile.user)
                engine.rebuild_profile()
                count += 1
            except Exception:
                pass
        self.message_user(request, f"{count} profils reconstruits.")
    rebuild_selected_profiles.short_description = \
        "Reconstruire les profils sélectionnés"


@admin.register(RecommendationCache)
class RecommendationCacheAdmin(admin.ModelAdmin):
    list_display    = ['user', 'context', 'is_stale',
                        'computed_at', 'products_count']
    list_filter     = ['context', 'is_stale']
    readonly_fields = ['computed_at', 'product_ids', 'scores']

    def products_count(self, obj):
        return len(obj.product_ids)
    products_count.short_description = 'Nb produits'
