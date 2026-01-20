from alembic import op
import sqlalchemy as sa

from CTFd.plugins.instancer_plugin.models import InstancerChallengeModel # type: ignore

revision = "xxxx_add_decay_params"
down_revision = "b3cd2598c7ea"
branch_labels = None
depends_on = None


def upgrade():
    table_name = InstancerChallengeModel.__table__.name
    op.add_column(
        table_name,
        sa.Column("initial", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        table_name,
        sa.Column("minimum", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        table_name,
        sa.Column("decay_base", sa.Float(), server_default="0.0", nullable=False),
    )
    op.add_column(
        table_name,
        sa.Column("decay_factor", sa.Float(), server_default="0.0", nullable=False),
    )

    # Optional: remove server defaults after backfill
    op.alter_column(table_name, "initial", server_default=None)
    op.alter_column(table_name, "minimum", server_default=None)
    op.alter_column(table_name, "decay_base", server_default=None)
    op.alter_column(table_name, "decay_factor", server_default=None)


def downgrade():
    op.drop_column(table_name, "decay_factor")
    op.drop_column(table_name, "decay_base")
    op.drop_column(table_name, "minimum")
    op.drop_column(table_name, "initial")
