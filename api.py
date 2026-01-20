from CTFd.api import CTFd_API_v1  # type: ignore
from CTFd.utils.decorators import authed_only  # type: ignore
from CTFd.utils.user import get_current_team  # type: ignore

from flask import request, Response
from flask_restx import Resource
import requests
from typing import Any
import os

from .util import logger

from .models import (
    get_chal,
    get_instance_id,
    find_chall_short_name,
    DeployedPort,
    get_team_flag
)

PLUGIN_PREFIX = "/plugins/instancer-plugin"

def do_instancer_request(method: str, endpoint: str, params: dict[str, str], stream: bool = False) -> requests.Response | str:
    api_token = os.environ["CTFD_INSTANCER_API_TOKEN"]
    instancer_url = os.environ["CTFD_INSTANCER_URL"]
    headers = {"Content-Type": "application/json",
               "Accept": "application/json",
               "X-API-Key": api_token}
    if not instancer_url.endswith("/"):
        instancer_url += "/"
    if not instancer_url.startswith("https://"):
        instancer_url = "https://" + instancer_url
    instancer_url += "api/v1/"
    try:
        res = requests.request(
            method, instancer_url + endpoint, json=params, headers=headers, stream=stream)
        return res
    except Exception:
        return "Request to instancer failed."


def query_instance_status(challenge_id: int) -> dict[str, Any] | tuple[str, int]:
    """
    Queries the challengeStatus of the instancer for the current team, the given challenge.
    If the request returns an error, the error message and an appropriate status are returned.
    Else, the json object is returned.

    :param challenge_id: ID of the challenge.
    :type challenge_id: int
    :return: see above.
    :rtype: dict[str, Any] | tuple[str, int]
    """
    chall_short_name = find_chall_short_name(challenge_id)

    if chall_short_name is None:
        return "Could not find challenge short name.", 500

    team_id = get_current_team().id
    instance_id = get_instance_id(challenge_id, team_id)

    params = {
        "challenge": chall_short_name,
        "team": str(team_id),
        "instance": str(instance_id)
    }

    res = do_instancer_request("GET", "challengeStatus", params)
    if isinstance(res, str):
        return res, 500
    res_data = res.json()

    if res.status_code != 200 or res_data["status"] != "success":
        return f"Cannot query instancer: " + res_data.get("error", "undefined error"), 500
    return res_data["data"]


@CTFd_API_v1.route(f"{PLUGIN_PREFIX}/instance")
class Instance(Resource):
    @staticmethod
    @authed_only
    def get():
        """ Used to query status information about the challenge and the associated instance. """
        challenge_id = request.args.get("challengeId", type=int)

        if challenge_id is None:
            return {
                "success": False,
                "message": "No challengeId provided!"
            }, 400

        res = query_instance_status(challenge_id)

        if isinstance(res, tuple):
            return {
                "success": False,
                "message": res[0]
            }, res[1]
        
        if res is None:
            return {
                "success": True,
                "data": {
                    "running": False
                }
            }, 200
        
        data = {}
        for key in ["image_built", "image_building", "files_ready", "files_building", "deployed", "expires"]:
            if key in res:
                data[key] = res[key]
        
        urls = []
        for deployed_port_data in res["ports"]:
            # TODO: deployed_port.description is currently ignored
            deployed_port = DeployedPort(**deployed_port_data)
            if not deployed_port.display:
                # do not show hidden ports to the user
                continue

            if deployed_port.type == "https":
                if not deployed_port.ssl:
                    print(
                        "[error] Got DeployedPort with type = 'https', but ssl = False ", flush=True)
                    continue
                port_str = ""
                if deployed_port.port != 443:
                    port_str += f":{deployed_port}"
                url = f"https://{deployed_port.hostname}{port_str}"
            else:
                if deployed_port.type != "tcp":
                    print(
                        f"[error] Got DeployedPort with unknown type = {deployed_port.type}", flush=True)
                    continue
                url = f"nc {' --ssl' if deployed_port.ssl else ''}{deployed_port.hostname} {deployed_port.port}"
        
            urls.append(url)

        data["urls"] = urls
        data["needs_deployment"] = get_chal(challenge_id).needs_deployment

        return {
            "success": True,
            "data": data
        }, 200

    @staticmethod
    @authed_only
    def post():
        """ Used to spawn an instance for the team """
        logger.debug("POST: instance")
        challenge_id = request.args.get("challengeId", type=int)
        if challenge_id is None:
            logger.debug("POST instance: challenge_id has not been provided.")
            return {
                "success": False,
                "message": "No challengeId provided!"
            }, 400
        
        if not get_chal(challenge_id).needs_deployment:
            return {
                "success": False,
                "message": "Challenge does not require deployment."
            }, 400

        chall_short_name = find_chall_short_name(challenge_id)

        logger.debug(f"POST instance: chall_short_name = {chall_short_name}")

        if chall_short_name is None:
            return {
                "success": False,
                "message": "Could not find challenge short name."
            }, 500

        team_id = get_current_team().id
        instance_id = get_instance_id(challenge_id, team_id)

        logger.debug(f"POST instance: query_instance_status: {challenge_id}, {team_id}, {instance_id}")
        status_res = query_instance_status(challenge_id)
        assert status_res is not None
        if isinstance(status_res, tuple):
            logger.debug(f"POST instance: query_instance_status failed: {status_res[0]}, {status_res[1]}")
            return {
                "success": False,
                "message": status_res[0]
            }, status_res[1]
        
        logger.debug(f"POST instance: query_instance_status = {status_res}")

        team_flag = get_team_flag(challenge_id, team_id)
        if team_flag is None:
            logger.debug("POST instance: no team flag found.")
            return {
                "success": False,
                "message": "Could not create challenge files because challenge has no associated flag."
            }, 400

        params = {
            "challenge": chall_short_name,
            "team": str(team_id),
            "instance": str(instance_id),
            "flag": team_flag,
        }
        logger.debug(f"POST instance: deploy_params = {params}")
        res = do_instancer_request("POST", "deployChallenge", params)
        if isinstance(res, str):
            logger.debug(f"POST instance: deployChallenge failed: {res}")
            return {
                "success": False,
                "message": res
            }, 500
        res_data = res.json()
        logger.debug(f"POST instance: deployChallenge result = {res.status_code}, {res_data}")

        if (res.status_code != 202 and res.status_code != 200) or (res_data["status"] != "success" and res_data["status"] != "building"):
            logger.debug(f"POST instance: deployChallenge reported error: {res_data.get('error', 'undefined error')}")
            return {
                "success": False,
                "message": "Instancer failed deployment with: " + res_data.get("error", "undefined error")
            }, 500

        return {
            "success": True,
        }, 200

    @staticmethod
    @authed_only
    def delete():
        """ Used to destroy an instance for a team. """
        challenge_id = request.args.get("challengeId", type=int)

        if challenge_id is None:
            return {
                "success": False,
                "message": "No challengeId provided!"
            }, 400

        if not get_chal(challenge_id).needs_deployment:
            return {
                "success": False,
                "message": "Challenge does not require deployment."
            }, 400

        chall_short_name = find_chall_short_name(challenge_id)

        if chall_short_name is None:
            return {
                "success": False,
                "message": "Could not find challenge short name."
            }, 500

        team_id = get_current_team().id
        instance_id = get_instance_id(challenge_id, team_id)

        params = {
            "challenge": chall_short_name,
            "team": str(team_id),
            "instance": str(instance_id)
        }

        res = do_instancer_request(
            "POST", "destroyChallengeDeployment", params)
        if isinstance(res, str):
            return {
                "success": False,
                "message": res
            }, 500
        res_data = res.json()

        if res.status_code != 200 or res_data["status"] != "success":
            return {
                "success": False,
                "message": f"Stopping instance failed with: " + res_data.get("error", "undefined error")
            }, 500

        return {
            "success": True,
        }, 200


@CTFd_API_v1.route(f"{PLUGIN_PREFIX}/files")
class File(Resource):
    @staticmethod
    @authed_only
    def get():
        """ Proxy for the file download. """
        challenge_id = request.args.get("challengeId", type=int)
        if challenge_id is None:
            return {
                "success": False,
                "message": "No challengeId provided!"
            }, 400

        chall_short_name = find_chall_short_name(challenge_id)

        if chall_short_name is None:
            return {
                "success": False,
                "message": "Could not find challenge short name."
            }, 500

        team_id = get_current_team().id

        get_params = {
            "challenge": chall_short_name,
            "team": str(team_id)
        }
        get_res = do_instancer_request(
            "GET", "getFiles", get_params, stream=True)

        if isinstance(get_res, str):
            return {
                "success": False,
                "message": get_res
            }, 500

        if get_res.status_code != 200:
            if get_res.status_code == 428:
                # files have not been built, build them
                team_flag = get_team_flag(challenge_id, team_id)

                if team_flag is None:
                    return {
                        "success": False,
                        "message": "Could not create challenge files because challenge has no associated flag."
                    }, 400

                build_params = {
                    "challenge": chall_short_name,
                    "team": str(team_id),
                    "flag": team_flag,
                    "force": False
                }
                build_res = do_instancer_request(
                    "POST", "buildFiles", build_params)

                if isinstance(build_res, str):
                    return {
                        "success": False,
                        "message": build_res
                    }, 500

                if build_res.status_code != 202:
                    return {
                        "success": False,
                        "message": f"Could not build challenge files: {build_res.json()['error']}"
                    }, 500

                # retry getting the flag files
                get_res = do_instancer_request(
                    "GET", "getFiles", get_params, stream=True)
                if isinstance(get_res, str):
                    return {
                        "success": False,
                        "message": get_res
                    }, 500

                if get_res.status_code != 200:
                    return {
                        "success": False,
                        "message": f"Could not get challenges files, even after building: {get_res.json()['error']}"
                    }, 500
            else:
                return {
                    "success": False,
                    "message": f"Could not get challenge files: {get_res.json()['error']}"
                }, 500

        def generate():
            for chunk in get_res.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk

        chall = get_chal(challenge_id)
        filename = f"{chall.category}_{chall.name.replace("-", "_")}" 
        headers = {
            "Content-Type": get_res.headers.get("Content-Type", "application/octet-stream"),
            "Content-Disposition": f"attachment; filename={filename}.tar"
        }

        return Response(
            generate(),
            headers=headers,
            status=200
        )
