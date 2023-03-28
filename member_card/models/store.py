from member_card.db import db

from sqlalchemy.orm import relationship


class Store(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    store_hash = db.Column(db.String(16), nullable=False, unique=True)
    access_token = db.Column(db.String(128), nullable=False)
    scope = db.Column(db.Text(), nullable=False)
    admin_storeuser_id = relationship(
        "StoreUser",
        primaryjoin="and_(StoreUser.store_id==Store.id, StoreUser.admin==True)",
    )
    storeusers = relationship(
        "StoreUser", backref="store", overlaps="admin_storeuser_id"
    )

    def __init__(self, store_hash, access_token, scope):
        self.store_hash = store_hash
        self.access_token = access_token
        self.scope = scope

    def __repr__(self):
        return "<Store id=%d store_hash=%s access_token=%s...%s scope=%s>" % (
            self.id,
            self.store_hash,
            self.access_token[0:3],
            self.access_token[-3:],
            self.scope,
        )
