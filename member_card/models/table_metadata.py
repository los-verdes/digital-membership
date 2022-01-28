from member_card.db import db


class TableMetadata(db.Model):
    __tablename__ = "table_metadata"
    table_name = db.Column(db.String, primary_key=True)
    attribute_name = db.Column(db.String, primary_key=True)
    attribute_value = db.Column(db.String)
