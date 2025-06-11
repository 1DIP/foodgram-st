from django.urls import path
from .views import RecipeShortLinkView

app_name = 'recipes'

urlpatterns = [
    path('api/recipes/<int:pk>/', RecipeShortLinkView.as_view(), name='recipe-short-link'),
]