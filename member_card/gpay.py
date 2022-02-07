import logging
import time

from flask import current_app
from google.auth import crypt as crypt_google
from google.auth import jwt as jwt_google
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

from member_card.passes import GooglePayPassClass, GooglePayPassObject

logger = logging.getLogger(__name__)

EXISTS_MESSAGE = """\
No changes will be made when saved by link. To update info, use update() or patch().
For an example, see https://developers.google.com/pay/passes/guides/get-started/implementing-the-api/engage-through-google-pay#update-state
"""
NOT_EXIST_MESSAGE = "Will be inserted when user saves by link/button for first time\n"


class GooglePassJwt(object):
    def __init__(
        self,
        audience,
        jwt_type,
        service_account_email_address,
        origins,
        service_account_file,
    ):
        self.audience = audience
        self.type = jwt_type
        self.iss = service_account_email_address
        self.origins = origins
        self.iat = int(time.time())
        self.payload = {}

        # signer for rsa-sha256. uses same private key used in o_auth2.0
        self.signer = crypt_google.RSASigner.from_service_account_file(
            service_account_file
        )

    def add_loyalty_class(self, resource_payload):
        self.payload.setdefault("loyaltyClasses", [])
        self.payload["loyaltyClasses"].append(resource_payload)

    def add_loyalty_object(self, resource_payload):
        self.payload.setdefault("loyaltyObjects", [])
        self.payload["loyaltyObjects"].append(resource_payload)

    def generate_unsigned_jwt(self):
        unsigned_jwt = {}
        unsigned_jwt["iss"] = self.iss
        unsigned_jwt["aud"] = self.audience
        unsigned_jwt["typ"] = self.type
        unsigned_jwt["iat"] = self.iat
        unsigned_jwt["payload"] = self.payload
        unsigned_jwt["origins"] = self.origins

        return unsigned_jwt

    def generate_signed_jwt(self):
        jwt_to_sign = self.generate_unsigned_jwt()
        signed_jwt = jwt_google.encode(self.signer, jwt_to_sign)

        return signed_jwt


class GooglePayApiClient(object):
    uri = "https://walletobjects.googleapis.com/walletobjects/v1"

    request_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json; charset=UTF-8",
    }

    def __init__(self, service_account_file, scopes):
        self._credentials = service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=scopes,
        )
        self._session = AuthorizedSession(self._credentials)

    ###############################
    #
    # Preparing server-to-server authorized API call with OAuth 2.0
    #
    # Use Google API client library to prepare credentials used to authorize a http client
    # See https://developers.google.com/identity/protocols/OAuth2ServiceAccount?authuser=2#authorizingrequests
    #
    # @return Credentials credentials - Service Account credential for OAuth 2.0 signed JWT grants.
    #
    ###############################
    # def make_oauth_credential():
    #     # the variables are in config file
    #     credentials =

    #     return credentials

    def request(
        self,
        method,
        resource_type,
        resource_id,
        json_payload=None,
        vertical_type="loyalty",
    ):

        path = f"{vertical_type}{resource_type.title()}"
        if method != "post":
            path = f"{vertical_type}{resource_type.title()}/{resource_id}"
        url = f"{self.uri}/{path}"
        logger.debug(
            f"Sending {method.upper()} request to {url=} (headers: {self.request_headers}, {json_payload=})"
        )
        request_kwargs = dict(
            url=url,
            headers=self.request_headers,
        )
        if json_payload is not None:
            request_kwargs["json"] = json_payload
        response = getattr(self._session, method)(**request_kwargs)
        if method == "get":
            self.handle_get_call_status_code(response, resource_type, resource_id, None)
        elif method == "post":
            self.handle_insert_call_status_code(
                response, resource_type, resource_id, None
            )
        elif method == "patch":
            self.handle_patch_call_status_code(
                response, resource_type, resource_id, None
            )

        return response

    #############################
    #
    #  output to explain various status codes from a get api call
    #
    #  @param requests.response get_call_response - response from a get call
    #  @param string id_type - identifier of type of get call.  "object" or "class"
    #  @param string id - unique identifier of pass for given id_type
    #  @param string check_class_id - optional. class_id to check for if object_id exists, and id_type == 'object'
    #  @return void
    #
    #############################
    def handle_get_call_status_code(
        self, get_call_response, id_type, id, check_class_id=None
    ):
        if (
            get_call_response.status_code == 200
        ):  # id resource exists for this issuer account
            logger.warning(f"{id_type}_id: ({id}) already exists. {EXISTS_MESSAGE}")

            # for object get, do additional check
            if id_type == "object":
                logger.debug(
                    f"checking if object's class_id matches target class_id:\n{get_call_response.json()=}"
                )
                class_id_of_object_id = get_call_response.json()["classId"]
                if (
                    class_id_of_object_id != check_class_id
                    and check_class_id is not None
                ):
                    raise ValueError(
                        f"the class_id of inserted object is ({class_id_of_object_id})."
                        #  it does not match the target class_id ({check_class_id}). the saved object will not have the class properties you expect."
                    )
        elif (
            get_call_response.status_code == 404
        ):  # id resource does not exist for this issuer account
            logger.warning(f"{id_type}_id: ({id}) does not exist. {NOT_EXIST_MESSAGE}")
        elif (
            get_call_response.status_code == 409
        ):  # id resource does not exist for this issuer account
            logger.warning(f"issue with request: {get_call_response.text}")
        else:
            raise ValueError(f"issue with getting id_type: {get_call_response.text}")

        return

    #############################
    #
    #  output to explain various status codes from a insert api call
    #
    #  @param requests.response insert_call_response - response from an insert call
    #  @param string id_type - identifier of type of get call.  "object" or "class"
    #  @param string id - unique identifier of pass for given id_type
    #  @param string check_class_id - optional. class_id to check for if object_id exists, and id_type == 'object'
    #  @param vertical_type vertical_type - optional. vertical_type to fetch class_id of existing object_id.
    #  @return void
    #
    #############################
    def handle_insert_call_status_code(
        self,
        insert_call_response,
        id_type,
        id,
        check_class_id=None,
        vertical_type="loyalty",
    ):
        if insert_call_response.status_code == 200:
            logger.info(f"{id_type}_id ({id}) insertion success!\n")
        elif (
            insert_call_response.status_code == 409
        ):  # id resource exists for this issuer account
            logger.warning(f"{id_type}_id: ({id}) already exists. {EXISTS_MESSAGE}")

            # for object insert, do additional check
            if id_type == "object":
                get_call_response = None
                # get existing object id data
                get_call_response = self.get_pass_object(
                    vertical_type=vertical_type, object_id=id
                )  # if it is a new object id, expected status is 409
                logger.debug(
                    f"checking if object's class_id matches target class_id:\n{get_call_response.json()=}"
                )
                class_id_of_object_id = get_call_response.json()["classId"]
                if (
                    class_id_of_object_id != check_class_id
                    and check_class_id is not None
                ):
                    raise ValueError(
                        f"the class_id of inserted object is ({class_id_of_object_id}). it does not match the target class_id ({check_class_id})."
                        #  the saved object will not have the class properties you expect."
                    )
        else:
            raise ValueError(f"{id_type} insert issue: {insert_call_response.text}")

        return

    def handle_patch_call_status_code(
        self,
        insert_call_response,
        id_type,
        id,
        check_class_id=None,
        vertical_type="loyalty",
    ):
        if insert_call_response.status_code == 200:
            logger.info(f"{id_type}_id ({id}) insertion success!\n")
        elif (
            insert_call_response.status_code == 409
        ):  # id resource exists for this issuer account
            logger.warning(f"{id_type}_id: ({id}) already exists. {EXISTS_MESSAGE}")

            # for object insert, do additional check
            if id_type == "object":
                get_call_response = None
                # get existing object id data
                get_call_response = self.get_pass_object(
                    vertical_type=vertical_type, object_id=id
                )  # if it is a new object id, expected status is 409
                logger.debug(
                    f"checking if object's class_id matches target class_id:\n{get_call_response.json()=}"
                )
                class_id_of_object_id = get_call_response.json()["classId"]
                if (
                    class_id_of_object_id != check_class_id
                    and check_class_id is not None
                ):
                    raise ValueError(
                        f"the class_id of inserted object is ({class_id_of_object_id}). it does not match the target class_id ({check_class_id})."
                        #  the saved object will not have the class properties you expect."
                    )
        else:
            raise ValueError(f"{id_type} insert issue: {insert_call_response.text}")

        return

    ###############################
    #
    # get existing class with google pay api for passes rest api
    #
    # see https://developers.google.com/pay/passes/reference/v1/
    #
    # @param vertical_type vertical_type - type of pass
    # @param string class_id - unique identifier for a class
    # @return requests.response response - response from rest call
    #
    ###############################
    def get_pass_class(self, class_id, vertical_type="loyalty"):
        # see if Ids exist in Google backend
        logger.debug(f"Making REST call to get {class_id=}")

        return self.request(
            method="get",
            resource_type="class",
            resource_id=class_id,
            vertical_type=vertical_type,
        )

    ###############################
    #
    # Get defined object with Google Pay API for Passes REST API
    #
    # See https://developers.google.com/pay/passes/reference/v1/
    #
    # @param String object_id - The unique identifier for an object.
    # @return requests.Response response - response from REST call
    #
    ###############################
    def get_pass_object(self, object_id, vertical_type="loyalty"):
        logger.debug(f"Making REST call to get {object_id=}")

        # if it is a new object Id, expected status is 409
        # check object get response. Will print out if object exists or not.
        # Throws error if object resource is malformed, or if existing object_id's classId does not match the expected classId

        # Define get() REST call of target vertical
        # There is no Google API for Passes Client Library for Python.
        # Authorize a http client with credential generated from Google API client library.
        # see https://google-auth.readthedocs.io/en/latest/user-guide.html#making-authenticated-requests

        # make the GET request to make an get(); this returns a response object
        # other methods require different http methods; for example, get() requires authed_Session.get(...)
        # check the reference API to make the right REST call
        # https://developers.google.com/pay/passes/reference/v1/
        # https://google-auth.readthedocs.io/en/latest/user-guide.html#making-authenticated-requests

        return self.request(
            method="get",
            resource_type="object",
            resource_id=object_id,
            vertical_type=vertical_type,
        )

    ###############################
    #
    # Insert class with Google Pay API for Passes REST API
    #
    # See https://developers.google.com/pay/passes/reference/v1/
    #
    # @param VerticalType verticalType - type of pass
    # @param Dict payload - represents class resource
    # @return requests.Response response - response from REST call
    #
    ###############################
    def insert_class(self, class_id, payload, vertical_type="loyalty"):
        logger.debug(f"Making REST call to insert class {class_id=}")
        # make authorized REST call to explicitly insert class into Google server.
        # if this is successful, you can check/update class definitions in Merchant Center GUI: https://pay.google.com/gp/m/issuer/list

        return self.request(
            method="post",
            resource_type="class",
            resource_id=class_id,
            json_payload=payload,
            vertical_type=vertical_type,
        )

    def patch_class(self, class_id, payload, vertical_type="loyalty"):
        logger.debug(f"Making REST call to patch class {class_id=}")
        # make authorized REST call to explicitly insert class into Google server.
        # if this is successful, you can check/update class definitions in Merchant Center GUI: https://pay.google.com/gp/m/issuer/list

        return self.request(
            method="patch",
            resource_type="class",
            resource_id=class_id,
            json_payload=payload,
            vertical_type=vertical_type,
        )

    ###############################
    #
    # Insert defined object with Google Pay API for Passes REST API
    #
    # See https://developers.google.com/pay/passes/reference/v1/
    #
    # @param VerticalType verticalType - represents type of pass being generated
    # @param Dict payload - represents class resource
    # @return requests.Response response - response from REST call
    #
    ###############################
    def insert_object(self, object_id, payload, vertical_type="loyalty"):
        logger.debug(f"Making REST call to insert object {object_id=}")
        # make authorized REST call to explicitly insert class into Google server.
        # if this is successful, you can check/update class definitions in Merchant Center GUI: https://pay.google.com/gp/m/issuer/list

        return self.request(
            method="post",
            resource_type="object",
            resource_id=object_id,
            json_payload=payload,
            vertical_type=vertical_type,
        )


def new_client():
    return GooglePayApiClient(
        service_account_file=current_app.config["GOOGLE_PAY_SERVICE_ACCOUNT_FILE"],
        scopes=current_app.config["GOOGLE_PAY_SCOPES"],
    )


def new_google_pass_jwt():
    return GooglePassJwt(
        audience=current_app.config["GOOGLE_PAY_AUDIENCE"],
        jwt_type=current_app.config["GOOGLE_PAY_JWT_TYPE"],
        service_account_email_address=current_app.config[
            "GOOGLE_PAY_SERVICE_ACCOUNT_EMAIL_ADDRESS"
        ],
        origins=current_app.config["GOOGLE_PAY_ORIGINS"],
        service_account_file=current_app.config["GOOGLE_PAY_SERVICE_ACCOUNT_FILE"],
    )


def generate_pass_jwt(membership_card):
    gpay_client = new_client()

    class_id = current_app.config["GOOGLE_PAY_PASS_CLASS_ID"]

    pass_class_payload = GooglePayPassClass(class_id).to_dict()

    pass_object_payload = GooglePayPassObject(class_id, membership_card).to_dict()
    object_id = pass_object_payload["id"]
    logger.debug(f"pass_object_payload => {object_id=}")

    insert_object_response = gpay_client.insert_object(
        object_id=object_id,
        payload=pass_object_payload,
    )
    logger.debug(f"{insert_object_response=}")

    logger.debug("Generating 'skinny' GPay pass JWT...")
    # put into JSON Web Token (JWT) format for Google Pay API for Passes
    google_pass_jwt = new_google_pass_jwt()
    google_pass_jwt.add_loyalty_class(pass_class_payload)
    google_pass_jwt.add_loyalty_object(pass_object_payload)

    # sign JSON to make signed JWT
    signed_jwt = google_pass_jwt.generate_signed_jwt()

    # See https://developers.google.com/pay/passes/guides/get-started/implementing-the-api/save-to-google-pay#add-link-to-email
    return signed_jwt
