import urllib.parse


class MemberCardException(Exception):
    def __init__(
        self, *args: object, form_error_message=None, form_message=None
    ) -> None:
        super().__init__(*args)
        self.form_error_message = form_error_message
        self.form_message = form_message

    def to_params(self):
        params = dict()
        if self.form_error_message:
            params["formErrorMessage"] = self.form_error_message
        if self.form_error_message:
            params["formMessage"] = self.form_message

        return urllib.parse.urlencode(params)
