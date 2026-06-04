"""add fs_uniquifier to users

Revision ID: e1a2b3c4d5e6
Revises: daad72fa8c6e
Create Date: 2026-06-03

flask-security-too >= 4.0 requires a fs_uniquifier column on the User model.
This migration adds the column (nullable initially), populates all existing
rows with a UUID, then tightens the constraint to NOT NULL + UNIQUE.
"""

import uuid

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e1a2b3c4d5e6"
down_revision = "897b8492d02b"
branch_labels = None
depends_on = None

users_table = sa.table(
    "users",
    sa.column("id", sa.Integer),
    sa.column("fs_uniquifier", sa.String(64)),
)


def upgrade():
    # Step 1: add the column as nullable so existing rows don't violate the constraint
    op.add_column(
        "users",
        sa.Column("fs_uniquifier", sa.String(length=64), nullable=True),
    )

    # Step 2: populate existing rows with a unique UUID each
    connection = op.get_bind()
    results = connection.execute(sa.select(users_table.c.id))
    for row in results:
        connection.execute(
            users_table.update()
            .where(users_table.c.id == row.id)
            .values(fs_uniquifier=str(uuid.uuid4()))
        )

    # Step 3: tighten to NOT NULL
    op.alter_column("users", "fs_uniquifier", nullable=False)

    # Step 4: add unique index
    op.create_unique_constraint("uq_users_fs_uniquifier", "users", ["fs_uniquifier"])


def downgrade():
    op.drop_constraint("uq_users_fs_uniquifier", "users", type_="unique")
    op.drop_column("users", "fs_uniquifier")
