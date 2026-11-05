from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _criar_usuario(self, email, password, **extra_fields):
        if not email:
            raise ValueError("O e-mail é obrigatório.")

        email = self.normalize_email(email)

        usuario = self.model(email=email, **extra_fields)

        usuario.set_password(password)

        usuario.save(using=self._db)

        return usuario

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)

        extra_fields.setdefault("is_superuser", False)

        extra_fields["perfil"] = (
            User.Perfil.ADMIN
            if extra_fields.get("is_staff")
            else User.Perfil.USUARIO
        )

        return self._criar_usuario(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)

        extra_fields.setdefault("is_superuser", True)

        extra_fields["perfil"] = User.Perfil.ADMIN

        if not extra_fields.get("is_staff") or not extra_fields.get("is_superuser"):
            raise ValueError("Superusuário deve ter is_staff e is_superuser ativos.")

        return self._criar_usuario(email, password, **extra_fields)


class User(AbstractUser):
    class Perfil(models.TextChoices):
        ADMIN = "admin", "Administrador"

        USUARIO = "user", "Usuário"

    username = None

    email = models.EmailField("e-mail", unique=True)

    nome = models.CharField("nome", max_length=150, db_column="name")

    perfil = models.CharField(
        "perfil",
        max_length=5,
        choices=Perfil.choices,
        default=Perfil.USUARIO,
        db_index=True,
        db_column="role",
    )

    date_joined = models.DateTimeField("data de cadastro", default=timezone.now, db_column="created_at")

    atualizado_em = models.DateTimeField(
        "data de atualização",
        auto_now=True,
        null=True,
        db_column="updated_at",
    )

    USERNAME_FIELD = "email"

    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = "users"

    def save(self, *args, **kwargs):
        self.nome = self.get_full_name().strip() or self.email

        self.perfil = self.Perfil.ADMIN if self.is_staff else self.Perfil.USUARIO

        campos_atualizados = kwargs.get("update_fields")

        if campos_atualizados is not None:
            campos_atualizados = set(campos_atualizados)

            if campos_atualizados.intersection({"first_name", "last_name", "email"}):
                campos_atualizados.add("nome")

            if "is_staff" in campos_atualizados:
                campos_atualizados.add("perfil")

            kwargs["update_fields"] = campos_atualizados

        super().save(*args, **kwargs)

    def __str__(self):
        return self.get_full_name() or self.email


# O nome registrado pelo Django permanece ``User`` porque alterá-lo depois da
# criação do projeto quebraria AUTH_USER_MODEL e o histórico de migrações.
# Todo o código de domínio utiliza este nome em português.
Usuario = User
