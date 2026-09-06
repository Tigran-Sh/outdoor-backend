from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('clubs', '0003_alter_teammember_team_role'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='teammember',
            name='team_role',
        ),
    ]
