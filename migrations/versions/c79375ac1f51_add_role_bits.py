"""Add role bits

Revision ID: c79375ac1f51
Revises: 97e73b85f5c4
Create Date: 2022-02-16 16:30:04.026866

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c79375ac1f51"
down_revision = "97e73b85f5c4"
branch_labels = None
depends_on = None


def upgrade():
    # jscpd:ignore-start
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "role",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "roles_users",
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("role_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["role.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
    )
    # ### end Alembic commands ###
    # jscpd:ignore-end
    sql = 'REASSIGN OWNED BY current_user TO "read_write"'
    op.execute(sql)


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("roles_users")
    op.drop_table("role")
    # ### end Alembic commands ###
