# Generated by Django 4.1.7 on 2023-03-06 13:38

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0008_remove_community_rules_community_created_at_and_more"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="community",
            unique_together={("account", "name")},
        ),
    ]