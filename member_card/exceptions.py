from flask import flash


class MemberCardException(Exception):
    def __init__(
        self, *args: object, form_error_message=None, form_message=None
    ) -> None:
        super().__init__(*args)
        self.form_error_message = form_error_message
        self.form_message = form_message

    def flash_em_if_you_got_em(self):
        if self.form_error_message:
            flash(self.form_error_message, "form-error")
        if self.form_message:
            flash(self.form_message, "error")
