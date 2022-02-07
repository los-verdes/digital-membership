#!/usr/bin/env python
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dateutil.parser import parse
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

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


def squarespace_orders_etl(squarespace_client, db_session, membership_sku, load_all):
    from member_card import models

    start_time = datetime.now(tz=ZoneInfo("UTC"))
    # db_session = get_db_session()
    instance = (
        db_session.query(models.TableMetadata)
        .filter_by(
            table_name=models.AnnualMembership.__tablename__,
            attribute_name="last_run_start_time",
        )
        .first()
    )
    # modified_before_dt = datetime.now(tz=ZoneInfo("UTC"))
    total_num_memberships_start = db_session.query(models.AnnualMembership.id).count()

    if instance and not load_all:
        logger.debug(f"{instance=}")
        last_run_start_time = datetime.fromtimestamp(float(instance.attribute_value))
        modified_after_dt = last_run_start_time - timedelta(days=1)
        logger.info(f"Starting sync from {last_run_start_time=}")
        # modified_after_dt = start_time - timedelta(days=3)
        modified_after = modified_after_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        modified_before = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        subscription_orders = squarespace_client.load_membership_orders_datetime_window(
            membership_sku=membership_sku,
            modified_after=modified_after,
            modified_before=modified_before,
        )

    else:
        subscription_orders = squarespace_client.load_all_membership_orders(
            membership_sku=membership_sku,
        )

    subscription_orders.reverse()
    member_user_ids_by_email = {}
    memberships = []
    logger.info(f"{len(subscription_orders)=} retrieved from Squarespace...")
    for subscription_order in subscription_orders:
        line_items = subscription_order.get("lineItems", [])
        subscription_line_items = [i for i in line_items if i["sku"] == membership_sku]
        for subscription_line_item in subscription_line_items:

            fulfilled_on = None
            if fulfilled_on := subscription_order.get("fulfilledOn"):
                fulfilled_on = parse(fulfilled_on)

            customer_email = subscription_order["customerEmail"]
            member_user_id = member_user_ids_by_email.get(customer_email)
            if member_user_id is None:
                member_user = get_or_create(
                    session=db_session,
                    model=models.User,
                    email=customer_email,
                )
                db.session.add(member_user)
                db.session.commit()
                member_user_id = member_user.id
                member_user_ids_by_email[customer_email] = member_user_id
            else:
                member_user = (
                    db_session.query(models.User).filter_by(id=member_user_id).one()
                )

            membership_kwargs = dict(
                order_id=subscription_order["id"],
                order_number=subscription_order["orderNumber"],
                user_id=member_user_id,
                channel=subscription_order["channel"],
                channel_name=subscription_order["channelName"],
                billing_address_first_name=subscription_order["billingAddress"][
                    "firstName"
                ],
                billing_address_last_name=subscription_order["billingAddress"][
                    "lastName"
                ],
                external_order_reference=subscription_order["externalOrderReference"],
                created_on=parse(subscription_order["createdOn"]),
                modified_on=parse(subscription_order["modifiedOn"]),
                fulfilled_on=fulfilled_on,
                customer_email=customer_email,
                fulfillment_status=subscription_order["fulfillmentStatus"],
                test_mode=subscription_order["testmode"],
                line_item_id=subscription_line_item["id"],
                sku=subscription_line_item["sku"],
                variant_id=subscription_line_item["variantId"],
                product_id=subscription_line_item["productId"],
                product_name=subscription_line_item["productName"],
            )
            membership = get_or_update(
                session=db_session,
                model=models.AnnualMembership,
                filters=["order_id", "order_number"],
                kwargs=membership_kwargs,
            )
            memberships.append(membership)
            if not member_user.fullname:
                member_name = f"{membership.billing_address_first_name} {membership.billing_address_last_name}"
                logger.debug(
                    f"No name set yet on {member_user=}, updating to: {member_name}"
                )
                member_user.fullname = member_name
                member_user.first_name = membership.billing_address_first_name
                member_user.last_name = membership.billing_address_last_name
                db.session.add(member_user)
            elif (
                member_user.first_name != membership.billing_address_first_name
                or member_user.last_name != membership.billing_address_last_name
            ):
                logger.warning(
                    f"{member_user.fullname=} does not match {membership.billing_address_first_name} {membership.billing_address_last_name} for some reason..."
                )
            db.session.add(membership)
            db.session.commit()

    cursor_metadata = get_or_create(
        session=db_session,
        model=models.TableMetadata,
        **dict(
            table_name=models.AnnualMembership.__tablename__,
            attribute_name="last_run_start_time",
        ),
    )
    setattr(cursor_metadata, "attribute_value", str(start_time.timestamp()))
    db.session.add(cursor_metadata)
    db_session.commit()

    active_memberships = [m for m in memberships if m.is_active]
    inactive_memberships = [m for m in memberships if not m.is_active]
    logger.info(
        f"Sync subscription sync run stats: {len(memberships)=} / {len(active_memberships)=} / {len(inactive_memberships)=}"
    )

    total_num_memberships_end = db_session.query(models.AnnualMembership.id).count()
    total_num_memberships_added = (
        total_num_memberships_end - total_num_memberships_start
    )
    logger.info(
        f"Sync subscription aggregate stats: {total_num_memberships_end=} - {total_num_memberships_start=} => {total_num_memberships_added=}"
    )
    return {
        "stats": dict(
            num_membership=len(memberships),
            num_active_membership=len(active_memberships),
            num_inactive_membership=len(inactive_memberships),
            total_num_memberships_start=total_num_memberships_start,
            total_num_memberships_end=total_num_memberships_end,
            total_num_memberships_added=total_num_memberships_added,
        )
    }


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
