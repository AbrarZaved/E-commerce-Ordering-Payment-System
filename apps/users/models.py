from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user keyed by a unique email instead of a username.

    We extend ``AbstractBaseUser`` (rather than ``AbstractUser``) because the
    assessment requires email-based authentication with no username field, and
    a clean, minimal identity model. See README design-decisions section.
    """

    email = models.EmailField("email address", unique=True)
    full_name = models.CharField(max_length=255, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email
