from member_card.db import db, get_or_create
from datetime import datetime


def get_last_run_start_time(table_name):
    from member_card.models import TableMetadata

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


def get_last_run_start_page(table_name):
    from member_card.models import TableMetadata

    last_run_start_page = (
        db.session.query(TableMetadata)
        .filter_by(
            table_name=table_name,
            attribute_name="last_run_start_page",
        )
        .first()
    )
    if last_run_start_page:
        return max(1, int(last_run_start_page.attribute_value))

    return 1


def set_last_run_start_page(table_name, last_run_start_page):
    from member_card.models import TableMetadata

    cursor_metadata = get_or_create(
        session=db.session,
        model=TableMetadata,
        **dict(
            table_name=table_name,
            attribute_name="last_run_start_page",
        ),
    )
    setattr(cursor_metadata, "attribute_value", last_run_start_page)
    db.session.add(cursor_metadata)
    db.session.commit()


class TableMetadata(db.Model):
    __tablename__ = "table_metadata"
    table_name = db.Column(db.String, primary_key=True)
    attribute_name = db.Column(db.String, primary_key=True)
    attribute_value = db.Column(db.String)
