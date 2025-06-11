from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

User = get_user_model()


@receiver(post_save, sender=User)
def handle_user_creation(sender, instance, created, **kwargs):
    """Обработка создания нового пользователя"""
    if created:
        # Дополнительная логика при создании пользователя
        pass