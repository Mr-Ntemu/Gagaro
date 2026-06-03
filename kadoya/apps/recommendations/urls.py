from django.urls import path
from .views import RecommendationAPIView, AnonymousRecommendationAPIView, TrackBehaviorView

app_name = 'recommendations'

urlpatterns = [
    path('', RecommendationAPIView.as_view(), name='api'),
    path('anonyme/', AnonymousRecommendationAPIView.as_view(), name='api_anonymous'),
    path('track/', TrackBehaviorView.as_view(), name='track'),
]
