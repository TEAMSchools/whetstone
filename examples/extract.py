import os
import json
import pathlib
import gzip

from dotenv import load_dotenv
import whetstone

# use `python-dotenv` to load environment variables defined in .env file
load_dotenv()

WHETSTONE_CLIENT_ID = os.getenv("WHETSTONE_CLIENT_ID")
WHETSTONE_CLIENT_SECRET = os.getenv("WHETSTONE_CLIENT_SECRET")
WHETSTONE_DISTRICT_ID = os.getenv("WHETSTONE_DISTRICT_ID")
WHETSTONE_CLIENT_CREDENTIALS = (WHETSTONE_CLIENT_ID, WHETSTONE_CLIENT_SECRET)
PROJECT_PATH = pathlib.Path(__file__).absolute().parent

# initialize client
ws = whetstone.Whetstone()
ws.authorize_client(client_credentials=WHETSTONE_CLIENT_CREDENTIALS)

# there's a subset of endpoints nexted under `generic-tags` to discover
# this will add them the list of endpoints to pull data from
generic_tags = ws.get("generic-tags").get("data")
generic_tags_endpoints = [f"generic-tags/{t}" for t in generic_tags]

endpoints = [
    "informals",
    "measurements",
    "meetings",
    "rubrics",
    "schools",
    "videos",
    "users",
    "assignments",
    "observations",
]

endpoints = generic_tags_endpoints + endpoints

for e in endpoints:
    print(e)
    e_clean = e.replace("generic-tags/", "")

    # create save foldre if it doesn't exist
    data_path = PROJECT_PATH / "data" / e_clean
    if not data_path.exists():
        data_path.mkdir(parents=True)
        print(f"\tCreated {'/'.join(data_path.parts[-3:])}...")

    # get all data from endpoint
    r = ws.get(e)
    count = r.get("count")
    print(f"\tFound {count} records...")

    # if records returned save to compressed json file
    if count > 0:
        data = r.get("data")
        data_file = data_path / f"{e_clean}.json.gz"
        with gzip.open(data_file, "wt", encoding="utf-8") as f:
            json.dump(data, f)
        print(f"\tSaved to {'/'.join(data_file.parts[-4:])}!")
