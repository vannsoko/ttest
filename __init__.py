from flask import Blueprint, render_template

from CTFd.exceptions.challenges import ChallengeCreateException # type: ignore
from CTFd.models import Challenges, Flags, db # type: ignore
from CTFd.plugins import register_plugin_assets_directory # type: ignore
from CTFd.plugins.challenges import CHALLENGE_CLASSES, BaseChallenge # type: ignore
from CTFd.plugins.migrations import upgrade # type: ignore


class InstancerChallengeModel(Challenges):
    __mapper_args__ = {"polymorphic_identity": "instancer"}
    id = db.Column(
        db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )

    def __init__(self, *args, **kwargs):
        super(InstancerChallengeModel, self).__init__(**kwargs)
        try:
            self.value = kwargs["value"]
        except KeyError:
            raise ChallengeCreateException("Missing value for challenge")


class InstancerChallenge(BaseChallenge):
    id = "instancer"  # Unique identifier used to register challenges
    name = "instancer"  # Name of a challenge type
    templates = (
        {  # Handlebars templates used for each aspect of challenge editing & viewing
            "create": "/plugins/instancer_plugin/assets/create.html",
            "update": "/plugins/instancer_plugin/assets/update.html",
            "view": "/plugins/instancer_plugin/assets/view.html",
        }
    )
    scripts = {  # Scripts that are loaded when a template is loaded
        "create": "/plugins/instancer_plugin/assets/create.js",
        "update": "/plugins/instancer_plugin/assets/update.js",
        "view": "/plugins/instancer_plugin/assets/view.js",
    }
    # Route at which files are accessible. This must be registered using register_plugin_assets_directory()
    route = "/plugins/instancer_plugin/assets/"
    # Blueprint used to access the static_folder directory.
    blueprint = Blueprint(
        "instancer_plugin",
        __name__,
        template_folder="templates",
        static_folder="assets",
    )
    challenge_model = InstancerChallengeModel

    @classmethod
    def create(cls, request):
        print("__init__.py: create", flush=True)
        data = request.form or request.get_json()
        challenge = cls.challenge_model(**data)
        db.session.add(challenge)
        db.session.commit()
        return challenge

    @classmethod
    def read(cls, challenge):
        """
        This method is in used to access the data of a challenge in a format processable by the front end.

        :param challenge:
        :return: Challenge object, data dictionary to be returned to the user
        """
        challenge = InstancerChallengeModel.query.filter_by(id=challenge.id).first()
        print("__init__.py: read", flush=True)
        return super().read(challenge)

    @classmethod
    def update(cls, challenge, request):
        """
        This method is used to update the information associated with a challenge. This should be kept strictly to the
        Challenges table and any child tables.

        :param challenge:
        :param request:
        :return:
        """
        data = request.form or request.get_json()
        print(f"__init__.py: update: {data}", flush=True)
        super().update(challenge, request)
        return challenge

    @classmethod
    def solve(cls, user, team, challenge, request):
        super().solve(user, team, challenge, request)


def load(app):
    print("Booting instancer-plugin", flush=True)
    upgrade(plugin_name="instancer_plugin")
    app.register_blueprint(InstancerChallenge.blueprint)
    CHALLENGE_CLASSES["instancer"] = InstancerChallenge
    register_plugin_assets_directory(
        app, base_path="/plugins/instancer_plugin/assets"
    )
    @app.route("/admin/instancer_route", methods=["GET"])
    def instancer_route():
        return render_template("page.html", content="<h1>BLA Page</h1>")
    
    # register API endpoints
    from . import api

    print("Init finished", flush=True)