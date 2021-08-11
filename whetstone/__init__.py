__version__ = "0.3.1"

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

    def _request(self, session_type, method, path, params={}, body=None):
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
        except requests.exceptions.HTTPError as e:
            response_json = response.json()
            print(
                f"{response_json['name']} {response_json['code']}\n{response_json['message']}"
            )
            print(e)
            raise e

    def authorize_client(self, **kwargs):
        """ """
        access_token = kwargs.get("access_token")
        client_credentials = kwargs.get("client_credentials")

        # check if access token supplied
        if access_token:
            # check if access token is still valid
            expires_at = datetime.fromtimestamp(access_token.get("expires_at"))
            now = datetime.now()
            if expires_at > now:
                self.access_token = access_token
                self.client_session.headers[
                    "Authorization"
                ] = f"Bearer {access_token.get('access_token')}"
                return "Authorized!"
            else:
                return "Access token expired!"

        # check for client credentials (tuple)
        if isinstance(client_credentials, tuple):
            client_id, client_secret = client_credentials
            print("Fetching new access token...")
            client = BackendApplicationClient(client_id=client_id)
            oauth = OAuth2Session(client=client)
            token = oauth.fetch_token(
                token_url=f"{self.base_url}/auth/client/token",
                client_id=client_id,
                client_secret=client_secret,
            )
            self.access_token = token
            self.client_session.headers[
                "Authorization"
            ] = f"Bearer {token.get('access_token')}"
            return "Authorized!"
        else:
            # exit - prompt for credientials tuple
            raise Exception(
                "You must provide a valid access token file or client credentials."
            )

    def authorize_frontend(self, district_id, username, password):
        print("Fetching new access token...")
        payload = {
            "username": username,
            "password": password,
            "grant_type": "password",
        }
        self.frontend_session.headers["district"] = district_id
        token = self._request(
            session_type="frontend", method="POST", path="auth/token", body=payload
        )
        self.frontend_access_token = token
        self.frontend_session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token.get('access_token')}",
            }
        )
        return "Authorized!"

    def get(self, schema, record_id=None, params={}, session_type="client"):
        """ """
        default_params = {"limit": self.api_response_limit, "skip": 0}
        default_params.update(params)

        if record_id:
            path = f"{schema}/{record_id}"
            response = self._request(
                method="GET", session_type=session_type, path=path, params=params
            )
            return {
                "count": 1,
                "limit": self.api_response_limit,
                "skip": 0,
                "data": [response],
            }
        elif schema in ["generic-tags", "roles"] or session_type == "frontend":
            response = self._request(
                method="GET",
                session_type=session_type,
                path=schema,
                params=default_params,
            )
            return response
        else:
            all_data = []
            while True:
                response = self._request(
                    method="GET",
                    session_type=session_type,
                    path=schema,
                    params=default_params,
                )
                data = response.get("data")
                all_data.extend(data)
                default_params["skip"] += default_params["limit"]
                if not data:
                    break
            response.update({"data": all_data})
            return response

    def post(self, schema, params={}, body=None, session_type="client"):
        response = self._request(
            method="POST",
            session_type=session_type,
            path=schema,
            params=params,
            body=body,
        )
        return response

    def put(self, schema, record_id, body=None, session_type="client"):
        path = f"{schema}/{record_id}"
        response = self._request(
            method="PUT", session_type=session_type, path=path, body=body
        )
        return response

    def delete(self, schema, record_id, session_type="client"):
        path = f"{schema}/{record_id}"
        response = self._request(
            method="DELETE",
            session_type=session_type,
            path=path,
        )
        return response
