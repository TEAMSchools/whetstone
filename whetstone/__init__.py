__version__ = "0.4.1"

from datetime import datetime

import requests
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session


class Whetstone:
    def __init__(self):
        self.base_url = f"https://api.whetstoneeducation.com"
        self.access_token = None
        self.api_response_limit = 100
        self.frontend_session = requests.Session()
        self.client_session = requests.Session()
        self.client_session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def _request(self, method, path, session_type="client", params={}, body=None):
        """ """
        if session_type == "client":
            url = f"{self.base_url}/external/{path}"
            session = self.client_session
        elif session_type == "frontend":
            url = f"{self.base_url}/{path}"
            session = self.frontend_session

        try:
            response = session.request(method=method, url=url, params=params, json=body)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as xc:
            print(xc)
            response_json = response.json()
            print(
                f"{response_json['name']} {response_json['code']}\n{response_json['message']}"
            )
            raise xc

    def _authorize_access_token(self, access_token):
        """
        check if access token is still valid
        """
        expires_at = datetime.fromtimestamp(access_token.get("expires_at"))
        now = datetime.now()
        if expires_at > now:
            return access_token
        else:
            raise Exception("Access token expired!")

    def _authorize_credentials(self, credentials):
        if isinstance(credentials, tuple):
            client_id, client_secret = credentials

            client = BackendApplicationClient(client_id=client_id)
            oauth = OAuth2Session(client=client)
            return oauth.fetch_token(
                token_url=f"{self.base_url}/auth/client/token",
                client_id=client_id,
                client_secret=client_secret,
            )
        else:
            return Exception("You must provide a valid credentials tuple!")

    def authorize_client(self, **kwargs):
        """ """
        access_token = kwargs.get("access_token")
        client_credentials = kwargs.get("client_credentials")

        # check if access token supplied
        if access_token:
            access_token = self._authorize_access_token(access_token=access_token)
        # check for client credentials (tuple)
        elif client_credentials:
            access_token = self._authorize_credentials(credentials=client_credentials)
        else:
            raise Exception(
                "You must provide a valid access token dict or credentials tuple!"
            )

        self.access_token = access_token
        self.client_session.headers[
            "Authorization"
        ] = f"Bearer {access_token.get('access_token')}"

    def authorize_frontend(self, district_id, username, password):
        payload = {
            "username": username,
            "password": password,
            "grant_type": "password",
        }
        self.frontend_session.headers["district"] = district_id
        token = self._request(
            method="POST", path="auth/token", session_type="frontend", body=payload
        )
        self.frontend_access_token = token
        return

    def get(self, schema, record_id=None, params={}, session_type="client"):
        """ """
        default_params = {"limit": self.api_response_limit, "skip": 0}
        default_params.update(params)

        if session_type == "frontend":
            response = self._request(
                method="GET",
                path=schema,
                session_type=session_type,
                params=default_params,
            )
            return response
        elif record_id:
            path = f"{schema}/{record_id}"
            response = self._request(
                method="GET", path=path, session_type=session_type, params=params
            )
            return {
                "count": 1,
                "limit": self.api_response_limit,
                "skip": 0,
                "data": [response],
            }
        else:
            all_data = []
            while True:
                response = self._request(
                    method="GET",
                    path=schema,
                    session_type=session_type,
                    params=default_params,
                )

                data = response.get("data")
                if len(all_data) >= response.get("count"):
                    break
                else:
                    all_data.extend(data)
                    default_params["skip"] += default_params["limit"]
            response.update({"data": all_data})
            return response

    def post(self, schema, params={}, body=None):
        response = self._request(
            method="POST",
            path=schema,
            params=params,
            body=body,
        )
        return response

    def put(self, schema, record_id, params={}, body=None):
        path = f"{schema}/{record_id}"
        response = self._request(method="PUT", path=path, params=params, body=body)
        return response

    def delete(self, schema, record_id):
        path = f"{schema}/{record_id}"
        response = self._request(
            method="DELETE",
            path=path,
        )
        return response
