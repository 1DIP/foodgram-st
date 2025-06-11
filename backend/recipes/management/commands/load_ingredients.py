import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from recipes.models import Ingredient


class Command(BaseCommand):
    help = "Загрузка ингредиентов из JSON файла"

    def handle(self, *args, **kwargs):
        file_path = os.path.join(settings.BASE_DIR, "data", "ingredients.json")

        if not os.path.exists(file_path):
            self.stderr.write(f"Файл {file_path} не найден.")
            return

        with open(file_path, "r", encoding="utf-8") as file:
            count = len(Ingredient.objects.bulk_create(
                Ingredient(**item) for item in json.load(file)
            ))

        self.stdout.write(
            self.style.SUCCESS(f"Загружено ингредиентов: {count}")
        )