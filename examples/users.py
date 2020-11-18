import os

from dotenv import load_dotenv
import pandas as pd
import whetstone


load_dotenv()

# load environment variables
WHETSTONE_CLIENT_ID = os.getenv("WHETSTONE_CLIENT_ID")
WHETSTONE_CLIENT_SECRET = os.getenv("WHETSTONE_CLIENT_SECRET")
WHETSTONE_USERNAME = os.getenv("WHETSTONE_USERNAME")
WHETSTONE_PASSWORD = os.getenv("WHETSTONE_PASSWORD")
WHETSTONE_DISTRICT_ID = os.getenv("WHETSTONE_DISTRICT_ID")
WHETSTONE_IMPORT_FILE = os.getenv("WHETSTONE_IMPORT_FILE")  # see example template
WHETSTONE_CLIENT_CREDENTIALS = (WHETSTONE_CLIENT_ID, WHETSTONE_CLIENT_SECRET)

# instantiate and auth whetstone client
ws = whetstone.Whetstone()
ws.authorize_client(client_credentials=WHETSTONE_CLIENT_CREDENTIALS)
ws.authorize_frontend(
    district_id=WHETSTONE_DISTRICT_ID,
    username=WHETSTONE_USERNAME,
    password=WHETSTONE_PASSWORD,
)

# get existing data
schools = ws.get("schools").get("data")
grades = ws.get("generic-tags/grades").get("data")
courses = ws.get("generic-tags/courses").get("data")
current_users = ws.get("users").get("data")
archive_users = ws.get("users", params={"archived": True}).get("data")
roles = ws.get("roles", session_type="frontend")  # frontend login required

users = current_users + archive_users
existing_users = pd.DataFrame(users).convert_dtypes()

# load users to import
import_users = pd.read_json(WHETSTONE_IMPORT_FILE).convert_dtypes()
import_users.user_internal_id = import_users.user_internal_id.astype("string")
import_users.coach_internal_id = import_users.coach_internal_id.astype("string")
import_users.inactive = import_users.inactive.astype(bool)
import_users = import_users.fillna("")

# join dataframes
merge_df = import_users.merge(
    right=existing_users,
    how="left",
    left_on="user_internal_id",
    right_on="internalId",
    suffixes=("", "_ws"),
)
merge_df.inactive_ws = merge_df.inactive_ws.fillna(False)
merge_users = merge_df.to_dict(orient="records")

# for each user
for u in merge_users:
    # if already inactive/archived in Whetstone, skip
    if u["inactive_ws"] == True and u["archivedAt"] is not pd.NA:
        continue

    print(f"{u['user_name']} ({u['user_internal_id']})")

    # get matching record for school, grade, course, user, coach
    school_match = next(iter([x for x in schools if x["name"] == u["school_name"]]), {})
    grade_match = next(iter([x for x in grades if x["name"] == u["grade_name"]]), {})
    course_match = next(iter([x for x in courses if x["name"] == u["course_name"]]), {})
    user_match = next(
        iter(
            [
                x
                for x in users
                if x.get("internalId") == u["user_internal_id"]
                and x.get("internalId") != ""
            ]
        ),
        {},
    )
    coach_match = next(
        iter(
            [
                x
                for x in users
                if x.get("internalId") == u["coach_internal_id"]
                and x.get("internalId") != ""
            ]
        ),
        {},
    )

    # get internal IDs
    user_id = user_match.get("_id")
    coach_id = coach_match.get("_id")
    school_id = school_match.get("_id")
    grade_id = grade_match.get("_id")
    course_id = course_match.get("_id")

    ## if no existing user match, create
    if not user_id:
        # build user creation payload
        create_payload = dict(
            name=u["user_name"],
            email=u["user_email"],
            districts=[WHETSTONE_DISTRICT_ID],
            school=school_id,
            internalId=u["user_internal_id"],
        )
        # post and retreive new user ID
        create_response = ws.post("users", body=create_payload)
        user_id = create_response.get("_id")
        print(f"\tCreated")

        # build update payload
        update_payload = dict(
            coach=coach_id,
            defaultInformation=dict(gradeLevel=grade_id, course=course_id,),
            internalId=u["user_internal_id"],
        )
        # update user with accounting ID
        ws.put("users", user_id, body=update_payload)
        print(f"\tUpdated")
    ## if existing user match, update
    else:
        update_payload = dict(
            name=u["user_name"],
            email=u["user_email"],
            coach=coach_id,
            defaultInformation=dict(
                school=school_id, gradeLevel=grade_id, course=course_id,
            ),
            inactive=u["inactive"],
        )
        ws.put("users", user_id, body=update_payload)
        print(f"\tUpdated")

    ## if rehired, reactivate (via frontend)
    if u["inactive"] == False and u["archivedAt"] is not pd.NA:
        reactivate_url = f"{ws.base_url}/users/{user_id}/archive"
        ws.frontend_session.put(reactivate_url, params={"value": False})
        print("\tReactivated")
    # if terminated, deactivate/archive
    elif u["inactive"] == True and u["archivedAt"] is pd.NA:
        ws.delete("users", user_id)
        print(f"\tArchived")

    ## add to observation group
    if school_match:
        # get all observation groups for matching school
        school_observation_groups = school_match.get("observationGroups") or []

        # get matching record for group and role
        role_match = next(iter([x for x in roles if x["name"] == u["role_name"]]), {})
        group_match = next(
            iter(
                [
                    x
                    for x in school_observation_groups
                    if x.get("name") == u["group_name"]
                ]
            ),
            {},
        )

        # get internal IDs
        role_id = role_match.get("_id")
        group_id = group_match.get("_id")

        # check if already a member of the group
        group_membership_match = next(
            iter([x for x in group_match[u["group_type"]] if x.get("_id") == user_id]),
            {},
        )

        # if not a member of group, add via frontend
        if u["inactive"] == False and not group_membership_match:
            update_query = dict(
                userId=user_id, roleId=role_id, schoolId=school_id, groupId=group_id,
            )
            ws.post("school-roles", params=update_query, session_type="frontend")
            print(f"\tAdded to {u['group_name']} as {role_match['name']}")
