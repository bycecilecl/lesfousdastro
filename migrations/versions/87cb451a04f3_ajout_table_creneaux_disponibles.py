"""ajout table creneaux disponibles

Revision ID: 87cb451a04f3
Revises: 631c2f493de5
Create Date: 2026-07-29 07:58:57.794363

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '87cb451a04f3'
down_revision = '631c2f493de5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "creneaux_disponibles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date_creneau", sa.Date(), nullable=False),
        sa.Column("disponible", sa.Boolean(), nullable=False),
        sa.Column("commande_id", sa.Integer(), nullable=True),
        sa.Column(
            "date_creation",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "date_reservation",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["commande_id"],
            ["commandes.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("commande_id"),
        sa.UniqueConstraint("date_creneau"),
    )

    op.create_index(
        "ix_creneaux_disponibles_commande_id",
        "creneaux_disponibles",
        ["commande_id"],
        unique=False,
    )

    op.create_index(
        "ix_creneaux_disponibles_date_creneau",
        "creneaux_disponibles",
        ["date_creneau"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_creneaux_disponibles_date_creneau",
        table_name="creneaux_disponibles",
    )

    op.drop_index(
        "ix_creneaux_disponibles_commande_id",
        table_name="creneaux_disponibles",
    )

    op.drop_table("creneaux_disponibles")