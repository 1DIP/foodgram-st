from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.safestring import mark_safe
from django.db.models import Count
from .models import (
    User,
    Subscription,
    Recipe,
    Ingredient,
    IngredientInRecipe,
    Favorite,
    ShoppingCart
)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Админка для пользователей"""

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    get_full_name.short_description = 'Полное имя'

    def get_avatar_preview(self, obj):
        if obj.avatar:
            return mark_safe(f'<img src="{obj.avatar.url}" width="50" height="50" />')
        return 'Нет аватара'
    get_avatar_preview.short_description = 'Аватар'

    def get_recipes_count(self, obj):
        return obj.recipes.count()
    get_recipes_count.short_description = 'Количество рецептов'

    def get_subscriptions_count(self, obj):
        return obj.users.count()
    get_subscriptions_count.short_description = 'Подписок'

    def get_followers_count(self, obj):
        return obj.authors.count()
    get_followers_count.short_description = 'Подписчиков'

    list_display = (
        'id',
        'username',
        'get_full_name',
        'email',
        'get_avatar_preview',
        'get_recipes_count',
        'get_subscriptions_count',
        'get_followers_count',
    )
    search_fields = ('username', 'email')
    ordering = ('id',)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """Админка подписок"""

    list_display = ('user', 'author')
    search_fields = ('user__email', 'author__email')


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    """Админка ингредиентов"""

    list_display = ('name', 'measurement_unit')
    list_filter = ('measurement_unit',)
    search_fields = ('name', 'measurement_unit')
    ordering = ('name',)


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    """Админка рецептов"""

    def get_ingredients_list(self, obj):
        ingredients = obj.recipe_ingredients.all()
        return mark_safe('<br>'.join([
            f'{ing.ingredient.name} - {ing.amount} {ing.ingredient.measurement_unit}'
            for ing in ingredients
        ]))
    get_ingredients_list.short_description = 'Ингредиенты'

    def get_image_preview(self, obj):
        if obj.image:
            return mark_safe(f'<img src="{obj.image.url}" width="50" height="50" />')
        return 'Нет изображения'
    get_image_preview.short_description = 'Изображение'

    def get_favorites_count(self, obj):
        return obj.favorites.count()
    get_favorites_count.short_description = 'В избранном у'

    list_display = (
        'id',
        'name',
        'cooking_time',
        'author',
        'get_favorites_count',
        'get_ingredients_list',
        'get_image_preview',
    )
    search_fields = ('name', 'author__username', 'author__email')
    list_filter = ('author', 'created_at')
    ordering = ('id',)


@admin.register(IngredientInRecipe)
class IngredientInRecipeAdmin(admin.ModelAdmin):
    """Админка ингредиентов в рецепте"""

    list_display = ('recipe', 'ingredient', 'amount')
    search_fields = ('recipe__name', 'ingredient__name')


@admin.register(Favorite, ShoppingCart)
class RecipeListAdmin(admin.ModelAdmin):
    """Админка избранного и корзины"""

    list_display = ('user', 'recipe')
    search_fields = ('user__email', 'recipe__name')
    list_filter = ('user',)