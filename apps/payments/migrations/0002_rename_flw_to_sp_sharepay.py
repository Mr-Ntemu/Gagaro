# Generated manually — renomme les champs Flutterwave → SharePay

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0001_initial'),
    ]

    operations = [
        # 1) Supprimer l'ancien index AVANT les rename (SQLite rebuild)
        migrations.RemoveIndex(
            model_name='paymentattempt',
            name='payments_pa_flw_tx__335dbb_idx',
        ),

        # 2) Renommer les champs flw_* → sp_*
        migrations.RenameField(
            model_name='paymentattempt',
            old_name='flw_tx_ref',
            new_name='sp_reference',
        ),
        migrations.RenameField(
            model_name='paymentattempt',
            old_name='flw_transaction_id',
            new_name='sp_transaction_id',
        ),
        migrations.RemoveField(
            model_name='paymentattempt',
            name='flw_ref',
        ),
        migrations.RenameField(
            model_name='paymentattempt',
            old_name='flw_init_response',
            new_name='sp_init_response',
        ),
        migrations.RenameField(
            model_name='paymentattempt',
            old_name='flw_webhook_payload',
            new_name='sp_webhook_payload',
        ),
        migrations.RenameField(
            model_name='paymentattempt',
            old_name='flw_verify_response',
            new_name='sp_verify_response',
        ),

        # 3) Ajouter le nouvel index
        migrations.AddIndex(
            model_name='paymentattempt',
            index=models.Index(fields=['sp_reference'], name='payments_pa_sp_ref_7a8e3f_idx'),
        ),
    ]
