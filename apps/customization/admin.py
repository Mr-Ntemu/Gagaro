from django.contrib import admin
from .models import FrameOption, CustomizationSession, EngravingFont

@admin.register(FrameOption)
class FrameOptionAdmin(admin.ModelAdmin):
    list_display  = ['label', 'product', 'material', 'width_cm',
                      'height_cm', 'extra_price', 'is_available', 'order']
    list_filter   = ['material', 'is_available', 'product__category']
    list_editable = ['extra_price', 'is_available', 'order']

@admin.register(CustomizationSession)
class CustomizationSessionAdmin(admin.ModelAdmin):
    list_display   = ['pk', 'product', 'user', 'status',
                       'current_step', 'computed_price', 'created_at']
    list_filter    = ['status', 'current_step']
    readonly_fields = ['session_key', 'computed_price', 'created_at', 'updated_at']
    search_fields  = ['user__email', 'product__title']

@admin.register(EngravingFont)
class EngravingFontAdmin(admin.ModelAdmin):
    list_display  = ['name', 'css_family', 'is_active', 'order']
    list_editable = ['is_active', 'order']
