#!/usr/bin/env python
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from dateutil.parser import parse
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()
logger = logging.getLogger(__name__)


def get_membership_table_last_sync():
    from member_card import models

    # TODO: figure out how to respond when db is "empty" and we get this sort of exception:
    # sqlalchemy.exc.NoResultFound: No row was found when one was required
    last_run_start_time = (
        db.session.query(models.TableMetadata)
        .filter_by(
            table_name=models.AnnualMembership.__tablename__,
            attribute_name="last_run_start_time",
        )
        .one()
    )
    membership_last_sync = datetime.fromtimestamp(
        float(
            last_run_start_time.attribute_value,
        )
    )
    return membership_last_sync


def get_or_update(session, model, filters, kwargs):
    filters = {f: kwargs[f] for f in filters if f in kwargs}
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    # for k, v in kwargs.items():
    #     logger.warning(f"{k} : {type(v)}")
    instance = session.query(model).filter_by(**filters).first()

    logger.debug(f"Getting or updatin' {model.__name__} matching {filters=}")
    if instance:
        for k, v in kwargs.items():
            setattr(instance, k, v)
        return instance
    else:
        instance = model(**kwargs)
        return instance


def get_or_create(session, model, **kwargs):
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    # for k, v in kwargs.items():
    #     logger.warning(f"{k} : {type(v)}")
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance
    else:
        logger.debug(f"Creating {model.__name__} with {kwargs=}")
        instance = model(**kwargs)
        # session.add(instance)
        # session.commit()
        return instance


def ensure_user_for_order(email, first_name, last_name):
    from member_card.models import User

    member_user = get_or_create(
        session=db.session,
        model=User,
        email=email,
    )

    if not member_user.fullname:
        member_name = f"{first_name} {last_name}"
        logger.debug(f"No name set yet on {member_user=}, updating to: {member_name}")
        member_user.fullname = member_name
        member_user.first_name = first_name
        member_user.last_name = last_name

    if member_user.first_name != first_name:
        logger.warning(
            f"{member_user.first_name=} does not match {first_name} for some reason..."
        )
    if member_user.last_name != last_name:
        logger.warning(
            f"{member_user.last_name=} does not match {last_name} for some reason..."
        )

    db.session.add(member_user)
    db.session.commit()


def ensure_order_in_database(order, membership_skus):
    from member_card.models import AnnualMembership

    membership_orders = []
    line_items = order.get("lineItems", [])
    subscription_line_items = [i for i in line_items if i["sku"] in membership_skus]
    for subscription_line_item in subscription_line_items:

        fulfilled_on = None
        if fulfilled_on := order.get("fulfilledOn"):
            fulfilled_on = parse(fulfilled_on).replace(tzinfo=timezone.utc)

        customer_email = order["customerEmail"]

        membership_kwargs = dict(
            order_id=order["id"],
            order_number=order["orderNumber"],
            channel=order["channel"],
            channel_name=order["channelName"],
            billing_address_first_name=order["billingAddress"]["firstName"],
            billing_address_last_name=order["billingAddress"]["lastName"],
            external_order_reference=order["externalOrderReference"],
            created_on=parse(order["createdOn"]).replace(tzinfo=timezone.utc),
            modified_on=parse(order["modifiedOn"]).replace(tzinfo=timezone.utc),
            fulfilled_on=fulfilled_on,
            customer_email=customer_email,
            fulfillment_status=order["fulfillmentStatus"],
            test_mode=order["testmode"],
            line_item_id=subscription_line_item["id"],
            sku=subscription_line_item["sku"],
            variant_id=subscription_line_item["variantId"],
            product_id=subscription_line_item["productId"],
            product_name=subscription_line_item["productName"],
        )
        membership = get_or_update(
            session=db.session,
            model=AnnualMembership,
            filters=["order_id", "order_number"],
            kwargs=membership_kwargs,
        )
        membership_orders.append(membership)

        member_user_id = ensure_user_for_order(
            email=membership.customer_email,
            first_name=membership.billing_address_first_name,
            last_name=membership.billing_address_last_name,
        )
        if not membership.user_id:
            logger.debug(
                f"No user_id set for {membership=}! Setting to: {member_user_id=}"
            )
            setattr(membership, "user_id", member_user_id)
    return membership_orders


def get_last_run_start_time(table_name):
    from member_card.models import TableMetadata

    # db.session = get_db.session()
    instance = (
        db.session.query(TableMetadata)
        .filter_by(
            table_name=table_name,
            attribute_name="last_run_start_time",
        )
        .first()
    )
    if instance:
        return datetime.fromtimestamp(float(instance.attribute_value))

    return datetime.fromtimestamp(0)


def set_last_run_start_time(table_name, last_run_dt):
    from member_card.models import TableMetadata

    cursor_metadata = get_or_create(
        session=db.session,
        model=TableMetadata,
        **dict(
            table_name=table_name,
            attribute_name="last_run_start_time",
        ),
    )
    setattr(cursor_metadata, "attribute_value", str(last_run_dt.timestamp()))
    db.session.add(cursor_metadata)
    db.session.commit()


def squarespace_orders_etl(squarespace_client, membership_skus, load_all):
    from member_card import models

    etl_start_time = datetime.now(tz=ZoneInfo("UTC"))

    membership_table_name = models.AnnualMembership.__tablename__

    if not load_all:
        last_run_start_time = get_last_run_start_time(membership_table_name)
        logger.info(f"Starting sync from {last_run_start_time=}")
        subscription_orders = squarespace_client.load_membership_orders_datetime_window(
            membership_skus=membership_skus,
            modified_before=last_run_start_time,
            modified_after=last_run_start_time - timedelta(days=1),
        )

    else:
        logger.info("Loading ALL orders now...")
        subscription_orders = squarespace_client.load_all_membership_orders(
            membership_skus=membership_skus,
        )

    logger.info(f"{len(subscription_orders)=} retrieved from Squarespace...")

    # Insert oldest orders first (so our internal membership ID generally aligns with order IDs...)
    subscription_orders.reverse()

    # Loop over all the raw order data and do the ETL bits
    memberships = []
    for subscription_order in subscription_orders:
        membership_orders = ensure_order_in_database(
            order=subscription_order,
            membership_skus=membership_skus,
        )
        for membership_order in membership_orders:
            db.session.add(membership_order)
        db.session.commit()
        memberships += membership_orders

    set_last_run_start_time(membership_table_name, etl_start_time)

    return memberships


def ensure_db_schemas(drop_first):
    # TODO: figure out how to make this all work better
    # metadata = MetaData()
    # metadata.create_all()
    # db.create_all()
    # from social_flask_sqlalchemy import models
    # from member_card.models import user
    from social_flask_sqlalchemy import models as social_flask_models

    from member_card import models
    from member_card.db import db

    doodads = [
        social_flask_models.PSABase,
        models.TableMetadata,
        models.AnnualMembership,
        models.MembershipCard,
        models.AppleDeviceRegistration,
        models.User,
    ]
    engine = db.engine
    if drop_first:
        logger.warning("Dropping all tables first!")
        # from sqlalchemy import Column, String

        # def add_column(engine, table_name, column):
        #     column_name = column.compile(dialect=engine.dialect)
        #     column_type = column.type.compile(engine.dialect)
        #     engine.execute(
        #         "ALTER TABLE %s ADD COLUMN %s %s"
        #         % (table_name, column_name, column_type)
        #     )

        # column = Column("qr_code_message", String, primary_key=True)
        # add_column(engine, models.MembershipCard.__tablename__, column)
        for doodad in doodads:
            logger.warning(f"Dropping {doodad}!")
            doodad.metadata.drop_all(engine)

    doodads.reverse()
    for doodad in doodads:
        logger.warning(f"Creating {doodad}!")
        doodad.metadata.create_all(engine)
