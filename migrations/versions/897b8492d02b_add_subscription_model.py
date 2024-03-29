"""Add subscription model

Revision ID: 897b8492d02b
Revises: 2d15cb59b42d
Create Date: 2024-03-08 13:57:12.431748

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "897b8492d02b"
down_revision = "2d15cb59b42d"
branch_labels = None
depends_on = None


def upgrade():
    # jscpd:ignore-start
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "subscription",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=True),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("customer_id", sa.String(length=32), nullable=True),
        sa.Column("customer_first_name", sa.String(length=64), nullable=True),
        sa.Column("customer_last_name", sa.String(length=64), nullable=True),
        sa.Column("customer_email", sa.String(length=120), nullable=True),
        sa.Column("product_name", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=True),
        sa.Column("shipping_address", sa.Text(), nullable=True),
        sa.Column("signup_date", sa.DateTime(), nullable=True),
        sa.Column("pause_date", sa.DateTime(), nullable=True),
        sa.Column("cancellation_date", sa.DateTime(), nullable=True),
        sa.Column("next_payment_date", sa.DateTime(), nullable=True),
        sa.Column("created_time", sa.DateTime(), nullable=True),
        sa.Column("last_modified", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###
    # jscpd:ignore-end
    sql = 'REASSIGN OWNED BY current_user TO "read_write"'
    op.execute(sql)


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("subscription")
    # ### end Alembic commands ###
