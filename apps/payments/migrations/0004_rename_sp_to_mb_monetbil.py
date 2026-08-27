# Generated manually — renomme les champs SharePay → Monetbil

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0003_update_choices_help_texts'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='paymentattempt',
            name='payments_pa_sp_ref_7a8e3f_idx',
        ),
        migrations.RenameField(
            model_name='paymentattempt',
            old_name='sp_reference',
            new_name='mb_payment_id',
        ),
        migrations.RenameField(
            model_name='paymentattempt',
            old_name='sp_transaction_id',
            new_name='mb_transaction_id',
        ),
        migrations.RenameField(
            model_name='paymentattempt',
            old_name='sp_init_response',
            new_name='mb_init_response',
        ),
        migrations.RenameField(
            model_name='paymentattempt',
            old_name='sp_webhook_payload',
            new_name='mb_webhook_payload',
        ),
        migrations.RenameField(
            model_name='paymentattempt',
            old_name='sp_verify_response',
            new_name='mb_verify_response',
        ),
        migrations.AddIndex(
            model_name='paymentattempt',
            index=models.Index(fields=['mb_payment_id'], name='payments_pa_mb_paym_9c2d4e_idx'),
        ),
    ]
