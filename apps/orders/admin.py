from django.contrib import admin
from .models import Cart, CartItem, Order, OrderItem, OrderStatusHistory

class OrderItemInline(admin.TabularInline):
    model         = OrderItem
    extra         = 0
    readonly_fields = ['product_title', 'unit_price', 'quantity',
                        'line_total', 'artisan_payout', 'commission_rate']
    can_delete    = False

class OrderStatusHistoryInline(admin.TabularInline):
    model         = OrderStatusHistory
    extra         = 0
    readonly_fields = ['old_status', 'new_status', 'changed_by', 'note', 'changed_at']
    can_delete    = False

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display    = ['reference', 'user', 'status', 'total_amount',
                        'delivery_city', 'created_at']
    list_filter     = ['status', 'delivery_city', 'created_at']
    search_fields   = ['reference', 'user__email', 'delivery_name', 'delivery_phone']
    readonly_fields = ['reference', 'subtotal', 'total_amount',
                        'payment_reference', 'paid_at', 'created_at', 'updated_at']
    inlines         = [OrderItemInline, OrderStatusHistoryInline]
    list_editable   = ['status']

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display  = ['__str__', 'user', 'total_items', 'created_at']
    readonly_fields = ['created_at', 'updated_at']
