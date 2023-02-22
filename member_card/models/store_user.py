from member_card.db import db


class StoreUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("store.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    admin = db.Column(db.Boolean, nullable=False, default=False)

    def __init__(self, store, user, admin=False):
        self.store_id = store.id
        self.user_id = user.id
        self.admin = admin

    def __repr__(self):
        return "<StoreUser id=%d user_id=%s store_id=%d  admin=%s>" % (
            self.id,
            self.user_id,
            self.store_id,
            self.admin,
        )
