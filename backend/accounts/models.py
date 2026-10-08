from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone

from accounts.phones import normalize_phone


class UserRole(models.TextChoices):
    CUSTOMER = "CUSTOMER", "Client"
    BTP_COMPANY = "BTP_COMPANY", "Entreprise BTP"
    FIELD_AGENT = "FIELD_AGENT", "Agent terrain"
    PROJECT_MANAGER = "PROJECT_MANAGER", "Chef de projet"
    ADMIN = "ADMIN", "Administrateur"
    SUPER_ADMIN = "SUPER_ADMIN", "Super-administrateur"


class KemtaPermission(models.TextChoices):
    VIEW_PROJECT = "VIEW_PROJECT", "Voir les projets"
    CREATE_PROJECT = "CREATE_PROJECT", "Créer des projets"
    EDIT_PROJECT = "EDIT_PROJECT", "Modifier des projets"
    MANAGE_PROJECT = "MANAGE_PROJECT", "Gérer les projets"
    UPLOAD_EVIDENCE = "UPLOAD_EVIDENCE", "Ajouter des preuves terrain"
    VALIDATE_EVIDENCE = "VALIDATE_EVIDENCE", "Valider des preuves terrain"
    VIEW_FINANCE = "VIEW_FINANCE", "Voir les finances"
    MANAGE_FINANCE = "MANAGE_FINANCE", "Gérer les finances"
    CREATE_OPPORTUNITY = "CREATE_OPPORTUNITY", "Créer des opportunités"
    APPLY_OPPORTUNITY = "APPLY_OPPORTUNITY", "Répondre aux opportunités"
    MANAGE_COMPANY = "MANAGE_COMPANY", "Gérer un profil entreprise"
    MANAGE_CATALOG = "MANAGE_CATALOG", "Gérer le catalogue BTP"
    MANAGE_SUBSCRIPTION = "MANAGE_SUBSCRIPTION", "Gérer les abonnements"
    MANAGE_USERS = "MANAGE_USERS", "Gérer les utilisateurs"
    MANAGE_SERVICE_REQUESTS = "MANAGE_SERVICE_REQUESTS", "Gérer les demandes"
    VIEW_AUDIT_LOGS = "VIEW_AUDIT_LOGS", "Consulter les journaux"
    ASSIGN_FIELD_AGENT = "ASSIGN_FIELD_AGENT", "Affecter des agents terrain"
    CREATE_FIELD_MISSION = "CREATE_FIELD_MISSION", "Créer des missions terrain"
    VIEW_FIELD_REPORT = "VIEW_FIELD_REPORT", "Consulter les rapports terrain"
    REVIEW_FIELD_REPORT = "REVIEW_FIELD_REPORT", "Valider ou corriger les rapports terrain"
    MANAGE_PROJECT_ISSUE = "MANAGE_PROJECT_ISSUE", "Gérer les problèmes de chantier"
    VIEW_ASSIGNED_MISSION = "VIEW_ASSIGNED_MISSION", "Voir ses missions terrain"
    EXECUTE_ASSIGNED_MISSION = "EXECUTE_ASSIGNED_MISSION", "Exécuter ses missions terrain"
    SUBMIT_FIELD_REPORT = "SUBMIT_FIELD_REPORT", "Soumettre un rapport terrain"
    REPORT_PROJECT_ISSUE = "REPORT_PROJECT_ISSUE", "Signaler un problème terrain"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, phone: str, password: str | None, **extra_fields):
        if not phone:
            raise ValueError("Un numéro de téléphone est requis.")
        try:
            normalized_phone = normalize_phone(phone)
        except Exception as exc:
            raise ValueError("Le numéro de téléphone doit être au format international valide.") from exc
        user = self.model(phone=normalized_phone, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, phone: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("role", UserRole.CUSTOMER)
        return self._create_user(phone, password, **extra_fields)

    def create_superuser(self, phone: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", UserRole.SUPER_ADMIN)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Un super-administrateur doit avoir is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Un super-administrateur doit avoir is_superuser=True.")
        return self._create_user(phone, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    phone = models.CharField(max_length=16, unique=True, db_index=True)
    phone_verified = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    email = models.EmailField(null=True, blank=True)
    role = models.CharField(max_length=24, choices=UserRole.choices, default=UserRole.CUSTOMER, db_index=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS: list[str] = ["first_name", "last_name"]

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("role", "is_active"))]

    def save(self, *args, **kwargs):
        if self.phone:
            self.phone = normalize_phone(self.phone)
        if self.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
            self.is_staff = True
        if self.email == "":
            self.email = None
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name} ({self.phone})".strip()


class RoleGrant(models.Model):
    role = models.CharField(max_length=24, choices=UserRole.choices)
    permission = models.CharField(max_length=40, choices=KemtaPermission.choices)
    enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("role", "permission"), name="uniq_role_permission")]
        indexes = [models.Index(fields=("role", "enabled"))]

    def __str__(self) -> str:
        return f"{self.role}: {self.permission}"
