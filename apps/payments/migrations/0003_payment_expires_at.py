from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0002_payment_items_snapshot_payment_user_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]