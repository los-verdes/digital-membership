from member_card.db import Model
from sqlalchemy import Column, String


class TableMetadata(Model):
    __tablename__ = "table_metadata"
    table_name = Column(String, primary_key=True)
    attribute_name = Column(String, primary_key=True)
    attribute_value = Column(String)
