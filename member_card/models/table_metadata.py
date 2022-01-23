from member_card.utils import get_db_session
from sqlalchemy import Column, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
Base.query = get_db_session().query_property()


class TableMetadata(Base):
    __tablename__ = "table_metadata"
    table_name = Column(String, primary_key=True)
    attribute_name = Column(String, primary_key=True)
    attribute_value = Column(String)
