from CTFd.api import CTFd_API_v1  # type: ignore
from flask import request
from flask_restx import Resource

from datetime import datetime, timedelta

PLUGIN_PREFIX = "/plugins/instancer-plugin"

instance_running = False
expires = None


@CTFd_API_v1.route(f"{PLUGIN_PREFIX}/instance")
class Instance(Resource):
    @staticmethod
    def get():
        global instance_running
        global expires
        challenge_id = request.args.get("challengeId", type=int)
        if challenge_id is None:
            return {
                "success": False,
                "message": f"No challengeId provided!"
            }, 400

        if not instance_running or expires is None:
            return {
                "success": True,
                "data": {
                    "running": instance_running,
                }
            }, 200

        return {
            "success": True,
            "data": {
                "running": instance_running,
                "expires": expires.isoformat(),
                "url": "https://some-challenge-1234abcdef.chals.ctf.h4tum.de:1337",
            }
        }, 200

    @staticmethod
    def post():
        global instance_running
        global expires
        challenge_id = request.args.get("challengeId", type=int)
        if challenge_id is None:
            return {
                "success": False,
                "message": f"No challengeId provided!"
            }, 400
        expires = datetime.now().astimezone() + timedelta(minutes=10)
        instance_running = True
        return {
            "success": True,
        }, 200

    @staticmethod
    def delete():
        global instance_running
        global expires
        challenge_id = request.args.get("challengeId", type=int)
        if challenge_id is None:
            return {
                "success": False,
                "message": f"No challengeId provided!"
            }, 400
        instance_running = False
        expires = None
        return {
            "success": True,
        }, 200
