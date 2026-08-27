# Generated manually — met à jour les choices, help_texts, phone_number

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0002_rename_flw_to_sp_sharepay'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentattempt',
            name='payment_method',
            field=models.CharField(
                choices=[
                    ('MTN_MOMO_CM', 'MTN Mobile Money'),
                    ('ORANGE_MONEY_CM', 'Orange Money'),
                ],
                default='MTN_MOMO_CM',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='paymentattempt',
            name='status',
            field=models.CharField(
                choices=[
                    ('initiated', 'Initié'),
                    ('pending', 'En attente confirmation client'),
                    ('processing', 'En cours de traitement'),
                    ('success', 'Succès'),
                    ('failed', 'Échec'),
                    ('timeout', 'Expiré'),
                    ('cancelled', 'Annulé'),
                ],
                default='initiated',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='paymentattempt',
            name='phone_number',
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
