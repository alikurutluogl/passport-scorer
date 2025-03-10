# libs for processing the deterministic stream location
import json
from typing import Dict, List

import api_logging as logging

# Making GET requests against the CERAMIC_URL to read streams
import requests
from ceramic_cache.models import CeramicCache
from django.conf import settings
from ninja_extra import status
from ninja_extra.exceptions import APIException

log = logging.getLogger(__name__)


class NoPassportException(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "No Passport found for this address."


# Location of a Ceramic node that we can read state from
CERAMIC_URL = "https://ceramic.passport-iam.gitcoin.co"

TRUSTED_IAM_ISSUER = settings.TRUSTED_IAM_ISSUER

# Service weights for scorer
SCORER_SERVICE_WEIGHTS = [
    {
        "ref": f"{TRUSTED_IAM_ISSUER}#Poh",
        "match_percent": 50,
    },
    {
        "ref": f"{TRUSTED_IAM_ISSUER}#POAP",
        "match_percent": 25,
    },
    {
        "ref": f"{TRUSTED_IAM_ISSUER}#Ens",
        "match_percent": 25,
    },
    {
        "ref": f"{TRUSTED_IAM_ISSUER}#Google",
        "match_percent": 15,
    },
    {
        "ref": f"{TRUSTED_IAM_ISSUER}#Twitter",
        "match_percent": 15,
    },
    {
        "ref": f"{TRUSTED_IAM_ISSUER}#Facebook",
        "match_percent": 15,
    },
    {
        "ref": f"{TRUSTED_IAM_ISSUER}#Brightid",
        "match_percent": 50,
    },
]

# Ceramic definition id for Gitcoin Passport
CERAMIC_GITCOIN_PASSPORT_STREAM_ID = (
    "kjzl6cwe1jw148h1e14jb5fkf55xmqhmyorp29r9cq356c7ou74ulowf8czjlzs"
)


def get_did(address, network="1"):
    # returns the did associated with the address on the given network
    return (f"did:pkh:eip155:{network}:{address}").lower()


def get_stream_ids(did, ids=[CERAMIC_GITCOIN_PASSPORT_STREAM_ID]):
    # return streams in a dict
    streams = {}

    try:
        # query and pin for the streamId
        stream_response = requests.post(
            f"{CERAMIC_URL}/api/v0/streams",
            json={
                "type": 0,
                "genesis": {
                    "header": {
                        "family": "IDX",
                        "controllers": [did],
                    },
                },
                "opts": {
                    "pin": True,
                    "anchor": False,
                },
            },
            timeout=10,
        )
        # get the state and default to empty content
        state = stream_response.json().get("state", {"content": {}})

        # check for a next record else pull from content
        content = state["next"]["content"] if state.get("next") else state["content"]

        # return streams for the given ids
        for linked_stream_id in ids:
            # pull CryptoAccounts streamID from expected location (kjzl6cwe1jw149z4rvwzi56mjjukafta30kojzktd9dsrgqdgz4wlnceu59f95f)
            streams[linked_stream_id] = (
                content[linked_stream_id].replace("ceramic://", "")
                if content.get(linked_stream_id)
                else False
            )
    except requests.exceptions.RequestException:
        pass
    except:
        pass

    # return the CryptoAccounts streamID (without the ceramic:// prefix)
    return streams


def get_passport(address: str = "", stream_ids: List[str] = []) -> Dict:
    did = get_did(address)

    db_stamp_list = CeramicCache.objects.filter(address=address)

    if len(db_stamp_list) == 0:
        # get streamIds if non are provided
        stream_ids = (
            stream_ids
            if len(stream_ids) > 0
            else get_stream_ids(did, [CERAMIC_GITCOIN_PASSPORT_STREAM_ID])
        )

        # attempt to pull content
        passport = get_stamps(get_passport_stream(stream_ids))

        # return a list of wallet address without the @eip155:1 suffix
        return passport
    else:
        return {
            "stamps": [
                {"provider": s.provider, "credential": s.stamp} for s in db_stamp_list
            ]
        }


def get_stamps(passport: Dict) -> Dict:
    if not passport:
        raise NoPassportException()

    # hydrate stamps contained within the passport
    if passport and passport["stamps"]:
        for index, stamp in enumerate(passport["stamps"]):
            passport["stamps"][index] = get_stamp_stream(stamp)

    return passport


def get_passport_stream(stream_ids=list()):
    # create an empty passport
    passport = {"stamps": []}

    try:
        # pull the CryptoAccounts streamID
        stream_id = stream_ids[CERAMIC_GITCOIN_PASSPORT_STREAM_ID]
        # get the stream content from given streamID
        stream_response = requests.get(
            f"{CERAMIC_URL}/api/v0/streams/{stream_id}", timeout=10
        )
        # get back the state object
        state = stream_response.json().get("state", {"content": {}})

        # check for a next record else pull from content
        passport = state["next"]["content"] if state.get("next") else state["content"]
    except requests.exceptions.RequestException:
        pass
    except:
        pass

    return passport


def get_stamp_stream(stamp: Dict) -> Dict:
    try:
        stamp["credential"] = stamp["credential"].replace("ceramic://", "")
        stamp_response = requests.get(
            f"{CERAMIC_URL}/api/v0/streams/{stamp['credential']}", timeout=10
        )
        # get back the state object
        state = stamp_response.json().get("state", {"content": {}})
        # check for a next record else pull from content
        stamp["credential"] = (
            state["next"]["content"] if state.get("next") else state["content"]
        )
    except requests.exceptions.RequestException:
        pass
    except:
        pass

    return stamp
