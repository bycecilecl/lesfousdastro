"""ajout heure aux creneaux

Revision ID: f9560248c101
Revises: 87cb451a04f3
Create Date: 2026-07-29 08:14:36.905454

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f9560248c101'
down_revision = '87cb451a04f3'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table(
        "creneaux_disponibles",
        schema=None,
    ) as batch_op:

        batch_op.add_column(
            sa.Column(
                "heure_creneau",
                sa.Time(),
                nullable=False,
            )
        )

        batch_op.drop_constraint(
            "creneaux_disponibles_date_creneau_key",
            type_="unique",
        )

        batch_op.create_unique_constraint(
            "uq_creneau_date_heure",
            ["date_creneau", "heure_creneau"],
        )


def downgrade():
    with op.batch_alter_table(
        "creneaux_disponibles",
        schema=None,
    ) as batch_op:

        batch_op.drop_constraint(
            "uq_creneau_date_heure",
            type_="unique",
        )

        batch_op.create_unique_constraint(
            "creneaux_disponibles_date_creneau_key",
            ["date_creneau"],
        )

        batch_op.drop_column("heure_creneau")