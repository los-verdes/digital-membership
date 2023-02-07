from datetime import datetime
from typing import TYPE_CHECKING

from member_card.db import db
from member_card.models import table_metadata

if TYPE_CHECKING:
    from flask import Flask


def test_get_last_run_start_time(app: "Flask"):
    table_name = table_metadata.TableMetadata.__tablename__

    with app.app_context():
        db.session.query(table_metadata.TableMetadata).filter_by(
            table_name=table_name
        ).delete()
        db.session.commit()

        last_run_start_time = table_metadata.get_last_run_start_time(
            table_name=table_metadata.TableMetadata.__tablename__,
        )
    assert last_run_start_time == datetime.fromtimestamp(0)

    test_last_run_dt = datetime.utcnow()

    with app.app_context():
        table_metadata.set_last_run_start_time(
            table_name=table_name,
            last_run_dt=test_last_run_dt,
        )
        last_run_start_time = table_metadata.get_last_run_start_time(
            table_name=table_name,
        )
    assert test_last_run_dt == last_run_start_time
