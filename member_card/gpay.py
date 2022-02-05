# For OAuth 2.0
from google.oauth2 import service_account  # pip install google-auth

# HTTP client For making REST API call with google-auth package
from google.auth.transport.requests import AuthorizedSession

from flask import current_app
import logging
import time
from google.auth import crypt as crypt_google
from google.auth import jwt as jwt_google
from textwrap import dedent

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
        if method == "get":
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


def generate_pass_jwt(membership_card):
    # signed_jwt = None
    # pass_class_payload = None
    # pass_object_payload = None
    # class_response = None
    # object_response = None
    # class_uid = f"LOYALTY_CLASS_{str(uuid.uuid4())}"

    # check Reference API for format of "id" (https://developers.google.com/pay/passes/reference/v1/o).
    # must be alphanumeric characters, '.', '_', or '-'.
    uid = "TESTLVMEMBERSHIP001"
    class_id = f"{current_app.config['GOOGLE_PAY_ISSUER_ID']}.CLASS{uid}"

    # check Reference API for format of "id" (https://developers.google.com/pay/passes/reference/v1/).
    # Must be alphanumeric characters, '.', '_', or '-'.
    object_id = f"{current_app.config['GOOGLE_PAY_ISSUER_ID']}.2OBJECT{uid}"

    logger.debug(f"{class_id=} | {object_id=}")
    print(f"{class_id=} | {object_id=}")

    gpay_client = GooglePayApiClient(
        service_account_file=current_app.config["GOOGLE_PAY_SERVICE_ACCOUNT_FILE"],
        scopes=current_app.config["GOOGLE_PAY_SCOPES"],
    )

    # get class definition and object definition
    logger.debug(f"Generating class resource for {class_id} ({membership_card=})")
    pass_class_payload = generate_pass_class(class_id, membership_card)
    logger.debug(f"Generating object resource for {class_id} ({membership_card=})")
    pass_object_payload = generate_pass_object_from_card(
        class_id, object_id, membership_card
    )

    # put into JSON Web Token (JWT) format for Google Pay API for Passes
    google_pass_jwt = GooglePassJwt(
        audience=current_app.config["GOOGLE_PAY_AUDIENCE"],
        jwt_type=current_app.config["GOOGLE_PAY_JWT_TYPE"],
        service_account_email_address=current_app.config[
            "GOOGLE_PAY_SERVICE_ACCOUNT_EMAIL_ADDRESS"
        ],
        origins=current_app.config["GOOGLE_PAY_ORIGINS"],
        service_account_file=current_app.config["GOOGLE_PAY_SERVICE_ACCOUNT_FILE"],
    )
    jwt_type = "skinny"

    if jwt_type == "object":
        logger.debug("Generating 'object' GPay pass JWT...")

        class_response = gpay_client.insert_class(
            class_id=class_id,
            payload=pass_class_payload,
        )
        logger.debug(f"{class_response=}")
        object_response = gpay_client.get_pass_object(object_id)
        logger.debug(f"{object_response=}")
        google_pass_jwt.add_loyalty_object(pass_object_payload)

    elif jwt_type == "skinny":
        logger.debug("Generating 'skinny' GPay pass JWT...")

        class_response = gpay_client.insert_class(
            class_id=class_id,
            payload=pass_class_payload,
        )
        logger.debug(f"{class_response=}")

        object_response = gpay_client.insert_object(
            object_id=object_id,
            payload=pass_object_payload,
        )
        logger.debug(f"{object_response=}")
        google_pass_jwt.add_loyalty_class(pass_class_payload)
        google_pass_jwt.add_loyalty_object(pass_object_payload)

    elif jwt_type == "fat":
        logger.debug("Generating 'fat' GPay pass JWT...")
        # for a Fat JWT, the first time a user hits the save button, the class and object are inserted
        class_response = gpay_client.get_pass_class(class_id)
        logger.debug(f"{class_response=}")

        logger.debug(f"Making REST call to get {object_id=} ({class_id=})")
        object_response = gpay_client.get_pass_object(object_id)
        logger.debug(f"{object_response=}")

        google_pass_jwt.add_loyalty_class(pass_class_payload)
        google_pass_jwt.add_loyalty_object(pass_object_payload)

    # sign JSON to make signed JWT
    signed_jwt = google_pass_jwt.generate_signed_jwt()

    # return "object" JWT. Try putting it into save link.
    # See https://developers.google.com/pay/passes/guides/get-started/implementing-the-api/save-to-google-pay#add-link-to-email
    return signed_jwt


###############################
#
# Define a Loyalty Class
#
# See https://developers.google.com/pay/passes/reference/v1/loyaltyclass
#
# @param String classId - The unique identifier for a class
# @return Dict payload - represents Loyalty class resource
#
###############################
def generate_pass_class(class_id, membership_card):
    # Define the resource representation of the Class
    # values should be from your DB/services; here we hardcode information

    payload = {}

    # below defines an Loyalty class. For more properties, check:
    # https://developers.google.com/pay/passes/reference/v1/loyaltyclass/insert
    # https://developers.google.com/pay/passes/guides/pass-verticals/loyalty/design

    payload = {
        # required fields
        "id": class_id,
        "issuerName": current_app.config["GOOGLE_PAY_ISSUER_NAME"],
        "programName": current_app.config["GOOGLE_PAY_PROGRAM_NAME"],
        "programLogo": {
            "kind": "walletobjects#image",
            "sourceUri": {
                "kind": "walletobjects#uri",
                "uri": membership_card.logo_uri,
            },
        },
        "reviewStatus": "underReview",  # optional
        "textModulesData": [
            {
                "header": membership_card.logo_text,
                "body": membership_card.description,
            }
        ],
        "linksModuleData": {
            # "uris": [
            #     {
            #         "kind": "walletobjects#uri",
            #         "uri": "http://maps.google.com/",
            #         "description": "Nearby Locations",
            #     },
            #     {
            #         "kind": "walletobjects#uri",
            #         "uri": "tel:6505555555",
            #         "description": "Call Customer Service",
            #     },
            # ]
        },
        "imageModulesData": [
            # {
            #     "mainImage": {
            #         "kind": "walletobjects#image",
            #         "sourceUri": {
            #             "kind": "walletobjects#uri",
            #             "uri": membership_card.icon_uri,
            #             "description": "#VHLM",
            #         },
            #     }
            # }
        ],
        "messages": [
            # {
            #     "header": "Welcome to Banconrista Rewards!",
            #     "body": "Featuring our new bacon donuts.",
            #     "kind": "walletobjects#walletObjectMessage",
            # }
        ],
        # "rewardsTier": "Gold",
        # "rewardsTierLabel": "Tier",
        "locations": [
            #     {
            #         "kind": "walletobjects#latLongPoint",
            #         "latitude": 37.424015499999996,
            #         "longitude": -122.09259560000001,
            #     },
            #     {
            #         "kind": "walletobjects#latLongPoint",
            #         "latitude": 37.424354,
            #         "longitude": -122.09508869999999,
            #     },
            #     {
            #         "kind": "walletobjects#latLongPoint",
            #         "latitude": 37.7901435,
            #         "longitude": -122.39026709999997,
            #     },
            #     {
            #         "kind": "walletobjects#latLongPoint",
            #         "latitude": 40.7406578,
            #         "longitude": -74.00208940000002,
            #     },
        ],
    }
    return payload


###############################
#
# Define a Loyalty Object
#
# See https://developers.google.com/pay/passes/reference/v1/loyaltyobject
#
# @param String classId - The unique identifier for a class
# @param String object_id - The unique identifier for an object
# @return Dict payload - represents Loyalty object resource
#
###############################
def generate_pass_object_from_card(class_id, object_id, membership_card):
    # Define the resource representation of the Object
    # values should be from your DB/services; here we hardcode information

    payload = {}

    # below defines an loyalty object. For more properties, check:
    # https://developers.google.com/pay/passes/reference/v1/loyaltyobject/insert
    # https://developers.google.com/pay/passes/guides/pass-verticals/loyalty/design

    payload = {
        # required fields
        "id": object_id,
        "classId": class_id,
        "state": "active",  # optional
        "accountId": membership_card.apple_pass_serial_number,
        "accountName": membership_card.user.fullname,
        # "barcode": {"alternateText": "12345", "type": "code128", "value": "28343E3"},
        "textModulesData": [
            {
                "header": "Los Verdes Membership Card",
                "body": dedent(
                    f"""\
                    {membership_card.user.fullname}
                    Member Since {membership_card.user.member_since.strftime("%b %Y")}
                    Good through {membership_card.user.membership_expiry.strftime("%b %d, %Y")}
                    """
                ),
            }
        ],
        "linksModuleData": {
            # "uris": [
            #     {
            #         "kind": "walletobjects#uri",
            #         "uri": "https://card.losverd.es",
            #         "description": "My Los Verdes Digital Membership Account",
            #     }
            # ]
        },
        "infoModuleData": {
            "labelValueRows": [
                {
                    "columns": [
                        {"label": "Next Reward in", "value": "2 coffees"},
                        {"label": "Member Since", "value": "01/15/2013"},
                    ]
                },
                {"columns": [{"label": "Local Store", "value": "Mountain View"}]},
            ],
            "showLastUpdateTime": "true",
        },
        "messages": [
            {
                "header": "Jane, welcome to Banconrista Rewards",
                "body": "Thanks for joining our program. Show this message to "
                + "our barista for your first free coffee on us!",
                "kind": "walletobjects#walletObjectMessage",
            }
        ],
        "loyaltyPoints": {"balance": {"string": "800"}, "label": "Points"},
        "locations": [
            {
                "kind": "walletobjects#latLongPoint",
                "latitude": 37.793484,
                "longitude": -122.394380,
            }
        ],
    }

    return payload
