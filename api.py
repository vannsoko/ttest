from CTFd.api import CTFd_API_v1  # type: ignore
from CTFd.utils.decorators import authed_only  # type: ignore
from CTFd.utils.user import get_current_team  # type: ignore

from flask import request, jsonify, Response
from flask_restx import Resource
from datetime import datetime
import requests
from typing import Any

from .models import (
    get_instance_id,
    update_instance_id,
    find_chall_short_name,
    DeployedPort,
    query_instance_urls,
    add_instance_url,
    remove_instance_urls,
    get_team_flag
)

PLUGIN_PREFIX = "/plugins/instancer-plugin"

# TODO: make this configurable
INSTANCER_URL = "https://localhost:1337/api/v1/"
API_TOKEN = "GENERIC_API_TOKEN_BLA"


def do_instancer_request(method: str, endpoint: str, params: dict[str, str], stream: bool = False) -> requests.Response | str:

    headers = {"Content-Type": "application/json",
               "Accept": "application/json",
               "X-API-Key": API_TOKEN}
    try:
        res = requests.request(
            method, INSTANCER_URL + endpoint, json=params, headers=headers, stream=stream)
        return res
    except Exception as e:
        return str(e)


def query_instance_status(challenge_id: int) -> None | dict[str, Any] | tuple[str, int]:
    """
    Queries the challengeStatus of the instancer for the current team, the given challenge.
    If there is no instance_id associated with (team, challenge), None is returned.
    If the request returns an error, the error message and an appropriate status are returned.
    Else, the json object is returned.

    :param challenge_id: ID of the challenge.
    :type challenge_id: int
    :return: see above.
    :rtype: dict[str, Any] | tuple[str, int] | None
    """
    chall_short_name = find_chall_short_name(challenge_id)

    if chall_short_name is None:
        return "Could not find challenge short name.", 500

    team_id = get_current_team().id
    instance_id = get_instance_id(challenge_id, team_id)

    if instance_id is None:
        return None

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
            return jsonify({
                "success": False,
                "message": "No challengeId provided!"
            }), 400

        res = query_instance_status(challenge_id)

        if isinstance(res, tuple):
            return jsonify({
                "success": False,
                "message": res[0]
            }), res[1]

        if res is None or "deployed" not in res:
            return jsonify({
                "success": True,
                "data": {
                    "running": False
                }
            }), 200

        expires = datetime.fromisoformat(res["expires"])

        if expires <= datetime.now():
            return jsonify({
                "success": True,
                "data": {
                    "running": False,
                }
            }), 200

        return jsonify({
            "success": True,
            "data": {
                "running": True,
                "expires": expires.isoformat(),
                "urls": query_instance_urls(challenge_id, get_current_team().id),
            }
        }), 200

    @staticmethod
    @authed_only
    def post():
        """ Used to spawn an instance for the team """
        challenge_id = request.args.get("challengeId", type=int)
        if challenge_id is None:
            return jsonify({
                "success": False,
                "message": "No challengeId provided!"
            }), 400

        chall_short_name = find_chall_short_name(challenge_id)

        if chall_short_name is None:
            return jsonify({
                "success": False,
                "message": "Could not find challenge short name."
            }), 500

        team_id = get_current_team().id
        instance_id = get_instance_id(challenge_id, team_id)
        if instance_id is None:
            update_instance_id(challenge_id, team_id, 1)
            instance_id = 1

            # the challenge image has not been built yet, build it
            build_params = {
                "challenge": chall_short_name,
                "team": str(team_id),
                "flag": get_team_flag(challenge_id, team_id),
                "force": False
            }
            img_build_res = do_instancer_request(
                "POST", "buildImage", build_params)
            if isinstance(img_build_res, str):
                return jsonify({
                    "success": False,
                    "error": img_build_res
                }), 500
            if img_build_res.status_code != 200:
                return jsonify({
                    "success": False,
                    "error": img_build_res.json()['error']
                }), img_build_res.status_code

        params = {
            "challenge": chall_short_name,
            "team": str(team_id),
            "instance": str(instance_id)
        }
        res = do_instancer_request("POST", "deployChallenge", params)
        if isinstance(res, str):
            return jsonify({
                "success": False,
                "error": res
            }), 500
        res_data = res.json()

        if res.status_code != 200 or res_data["status"] != "success":
            return jsonify({
                "success": False,
                "message": f"Instancer failed deployment with: " + res_data.get("error", "undefined error")
            }), 500
        res_data = res_data["data"]

        for deployed_port_data in res_data:
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
                url = f"nc {' -ssl' if deployed_port.ssl else ''}{deployed_port.hostname} {deployed_port.port}"

            add_instance_url(challenge_id, team_id, url)

        return jsonify({
            "success": True,
        }), 200

    @staticmethod
    @authed_only
    def delete():
        """ Used to destroy an instance for a team. """
        challenge_id = request.args.get("challengeId", type=int)

        if challenge_id is None:
            return jsonify({
                "success": False,
                "message": "No challengeId provided!"
            }), 400

        chall_short_name = find_chall_short_name(challenge_id)

        if chall_short_name is None:
            return jsonify({
                "success": False,
                "message": "Could not find challenge short name."
            }), 500

        team_id = get_current_team().id
        instance_id = get_instance_id(challenge_id, team_id)

        if instance_id is None:
            return jsonify({
                "success": False,
                "error": "No instance running for team."
            }), 200

        params = {
            "challenge": chall_short_name,
            "team": str(team_id),
            "instance": str(instance_id)
        }

        res = do_instancer_request(
            "POST", "destroyChallengeDeployment", params)
        if isinstance(res, str):
            return jsonify({
                "success": False,
                "error": res
            }), 500
        res_data = res.json()

        if res.status_code != 200 or res_data["status"] != "success":
            return jsonify({
                "success": False,
                "message": f"Stopping instance failed with: " + res_data.get("error", "undefined error")
            }), 500

        remove_instance_urls(challenge_id, team_id)

        return jsonify({
            "success": True,
        }), 200


@CTFd_API_v1.route(f"{PLUGIN_PREFIX}/files")
class File(Resource):
    @staticmethod
    @authed_only
    def get():
        """ Proxy for the file download. """
        challenge_id = request.args.get("challengeId", type=int)
        if challenge_id is None:
            return jsonify({
                "success": False,
                "message": "No challengeId provided!"
            }), 400

        chall_short_name = find_chall_short_name(challenge_id)

        if chall_short_name is None:
            return jsonify({
                "success": False,
                "message": "Could not find challenge short name."
            }), 500

        team_id = get_current_team().id

        get_params = {
            "challenge": chall_short_name,
            "team": str(team_id)
        }
        get_res = do_instancer_request(
            "GET", "getFiles", get_params, stream=True)

        if isinstance(get_res, str):
            return jsonify({
                "success": False,
                "error": get_res
            }), 500

        if get_res.status_code != 200:
            if get_res.status_code == 428:
                # files have not been built, build them
                team_flag = get_team_flag(challenge_id, team_id)

                if team_flag is None:
                    return jsonify({
                        "success": False,
                        "message": "Could not create challenge files because challenge has no associated flag."
                    }), 400

                build_params = {
                    "challenge": chall_short_name,
                    "team": str(team_id),
                    "flag": team_flag,
                    "force": False
                }
                build_res = do_instancer_request(
                    "POST", "buildFiles", build_params)

                if isinstance(build_res, str):
                    return jsonify({
                        "success": False,
                        "error": build_res
                    }), 500

                if build_res.status_code != 202:
                    return jsonify({
                        "success": False,
                        "message": f"Could not build challenge files: {build_res.json()['error']}"
                    }), 500

                # retry getting the flag files
                get_res = do_instancer_request(
                    "GET", "getFiles", get_params, stream=True)
                if isinstance(get_res, str):
                    return jsonify({
                        "success": False,
                        "error": get_res
                    }), 500

                if get_res.status_code != 200:
                    return jsonify({
                        "success": False,
                        "message": f"Could not get challenges files, even after building: {get_res.json()['error']}"
                    }), 500
            else:
                return jsonify({
                    "success": False,
                    "message": f"Could not get challenge files: {get_res.json()['error']}"
                }), 500

        def generate():
            for chunk in get_res.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk

        headers = {
            "Content-Type": get_res.headers.get("Content-Type", "application/octet-stream"),
            "Content-Disposition": get_res.headers.get(
                "Content-Disposition",
                "attachment; filename=chall_files.bin"
            )
        }

        return Response(
            generate(),
            headers=headers,
            status=200
        )
