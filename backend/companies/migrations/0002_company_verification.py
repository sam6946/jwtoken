"""Dossier de vérification des entreprises.

Migration purement additive : aucune colonne ni relation existante n'est modifiée
ou supprimée. Les valeurs par défaut (`DRAFT`, `ACCOUNT`, `Cameroun`) sont
appliquées aux entreprises déjà enregistrées, puis une étape de données aligne les
profils déjà vérifiés sur le nouveau statut.
"""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def align_existing_companies(apps, schema_editor):
    """Aligne les entreprises existantes sur les nouveaux champs de vérification."""
    CompanyProfile = apps.get_model("companies", "CompanyProfile")
    to_update = []
    for company in CompanyProfile.objects.all().iterator():
        if not company.legal_name:
            company.legal_name = company.name
        if company.verified:
            company.verification_status = "VERIFIED"
            company.verification_level = "BUSINESS_VERIFIED"
        else:
            company.verification_status = "DRAFT"
            company.verification_level = "ACCOUNT"
        to_update.append(company)
    if to_update:
        CompanyProfile.objects.bulk_update(
            to_update, ["legal_name", "verification_status", "verification_level"], batch_size=200
        )


def noop_reverse(apps, schema_editor):
    """Réversible sans perte : les colonnes ajoutées disparaissent avec la migration."""


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='address',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='advanced_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='company_type',
            field=models.CharField(blank=True, choices=[('SARL', 'SARL'), ('SA', 'SA'), ('SAS', 'SAS'), ('ETS', 'Établissement'), ('EI', 'Entreprise individuelle'), ('GIE', 'GIE'), ('COOPERATIVE', 'Coopérative'), ('AUTRE', 'Autre')], max_length=20),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='country',
            field=models.CharField(default='Cameroun', max_length=80),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='email',
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='legal_name',
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='phone',
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='registration_number',
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='sector',
            field=models.CharField(blank=True, db_index=True, max_length=80),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='tax_number',
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='verification_level',
            field=models.CharField(choices=[('ACCOUNT', 'Compte créé'), ('PROFILE', 'Profil complété'), ('BUSINESS_VERIFIED', 'Entreprise vérifiée'), ('ADVANCED', 'Vérification renforcée')], db_index=True, default='ACCOUNT', max_length=20),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='verification_rejection_reason',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='verification_reviewed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='verification_reviewed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='company_verifications_reviewed', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='verification_status',
            field=models.CharField(choices=[('DRAFT', 'Informations à compléter'), ('PENDING', 'Vérification en attente'), ('UNDER_REVIEW', 'En cours d’examen'), ('VERIFIED', 'Entreprise vérifiée'), ('REJECTED', 'Vérification non validée'), ('SUSPENDED', 'Vérification suspendue')], db_index=True, default='DRAFT', max_length=20),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='verification_submitted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='website',
            field=models.URLField(blank=True, max_length=300),
        ),
        migrations.CreateModel(
            name='CompanyDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('document_type', models.CharField(choices=[('RCCM', 'RCCM'), ('NIU', 'NIU'), ('REGISTRATION_CERTIFICATE', 'Document d’immatriculation'), ('IDENTITY_DOCUMENT', 'Pièce d’identité du représentant légal'), ('ADDRESS_PROOF', 'Preuve d’adresse'), ('OTHER', 'Autre document')], db_index=True, max_length=32)),
                ('file', models.FileField(upload_to='companies/documents/%Y/%m/')),
                ('original_name', models.CharField(blank=True, max_length=255)),
                ('content_type', models.CharField(blank=True, max_length=120)),
                ('file_size', models.PositiveIntegerField(default=0)),
                ('status', models.CharField(choices=[('PENDING', 'À vérifier'), ('APPROVED', 'Validé'), ('REJECTED', 'À corriger')], db_index=True, default='PENDING', max_length=20)),
                ('rejection_reason', models.CharField(blank=True, max_length=500)),
                ('uploaded_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documents', to='companies.companyprofile')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='company_documents_reviewed', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('document_type', '-uploaded_at'),
                'indexes': [models.Index(fields=['company', 'document_type', 'status'], name='companies_c_company_4c9f40_idx')],
                'constraints': [models.UniqueConstraint(condition=models.Q(('document_type', 'OTHER'), _negated=True), fields=('company', 'document_type'), name='uniq_company_document_type')],
            },
        ),
        migrations.RunPython(align_existing_companies, noop_reverse),
    ]
