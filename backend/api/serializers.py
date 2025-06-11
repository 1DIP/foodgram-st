from django.core.validators import MinValueValidator
from djoser.serializers import UserSerializer as DjoserUserSerializer
from drf_extra_fields.fields import Base64ImageField
from recipes.models import (
    Favorite,
    Ingredient,
    IngredientInRecipe,
    Recipe,
    ShoppingCart,
    Subscription,
    User,
)
from rest_framework import serializers


class UserSerializer(DjoserUserSerializer):
    """Сериализатор пользователя с подпиской"""

    is_subscribed = serializers.SerializerMethodField()
    avatar = Base64ImageField(required=False)

    class Meta(DjoserUserSerializer.Meta):
        fields = (
            *DjoserUserSerializer.Meta.fields,
            'avatar',
            'is_subscribed'
        )

    def get_is_subscribed(self, obj):
        user = self.context['request'].user
        return Subscription.objects.filter(
            author=obj.id,
            user=user.id
        ).exists()


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор ингредиентов"""

    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class IngredientInRecipeSerializer(serializers.ModelSerializer):
    """Сериализатор ингредиентов в рецепте"""

    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all(),
        source='ingredient.id'
    )
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit'
    )
    amount = serializers.IntegerField(min_value=1)

    class Meta:
        model = IngredientInRecipe
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeSerializer(serializers.ModelSerializer):
    """Сериализатор рецептов"""

    author = UserSerializer(read_only=True)
    ingredients = IngredientInRecipeSerializer(
        source='recipe_ingredients', many=True
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = (
            'id',
            'name',
            'text',
            'image',
            'author',
            'cooking_time',
            'ingredients',
            'is_favorited',
            'is_in_shopping_cart',
        )

    def create(self, validated_data):
        ingredients_data = validated_data.pop('recipe_ingredients')
        recipe = super().create(validated_data)
        self.add_ingredients(recipe, ingredients_data)
        return recipe

    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop('recipe_ingredients')
        instance.ingredients.clear()
        self.add_ingredients(instance, ingredients_data)
        return super().update(instance, validated_data)

    def add_ingredients(self, recipe, ingredients_data):
        IngredientInRecipe.objects.bulk_create(
            IngredientInRecipe(
                recipe=recipe,
                ingredient=ingredient['ingredient']['id'],
                amount=ingredient['amount']
            )
            for ingredient in ingredients_data
        )

    def check_recipe_status(self, model, recipe):
        request = self.context.get('request')
        return (
            request.user.is_authenticated
            and model.objects.filter(
                user=request.user,
                recipe=recipe
            ).exists()
        )

    def get_is_favorited(self, obj):
        return self.check_recipe_status(Favorite, obj)

    def get_is_in_shopping_cart(self, obj):
        return self.check_recipe_status(ShoppingCart, obj)


class ShortRecipeSerializer(serializers.ModelSerializer):
    """Краткий сериализатор рецепта"""

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')
        read_only_fields = ('id', 'name', 'image', 'cooking_time')


class UserWithRecipesSerializer(UserSerializer):
    """Сериализатор пользователя с рецептами"""

    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.ReadOnlyField(
        source='author.recipes.count'
    )

    class Meta(UserSerializer.Meta):
        fields = (
            *UserSerializer.Meta.fields,
            'recipes',
            'recipes_count',
        )

    def get_recipes(self, obj):
        return ShortRecipeSerializer(
            obj.recipes.all()[:int(self.context.get('request').GET.get(
                'recipes_limit',
                10**10
            ))],
            many=True
        ).data


class SubscriptionSerializer(serializers.ModelSerializer):
    """Сериализатор подписки"""
    user = serializers.StringRelatedField()
    author = serializers.StringRelatedField()

    class Meta:
        model = Subscription
        fields = ('user', 'author')