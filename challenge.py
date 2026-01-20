from flask import Blueprint

from CTFd.models import db  # type: ignore
from CTFd.plugins.challenges import BaseChallenge, Solves # type: ignore
from CTFd.utils.modes import get_model # type: ignore

from .models import InstancerChallengeModel

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
    route = "/plugins/instancer_plugin/assets"
    # Blueprint used to access the static_folder directory.
    blueprint = Blueprint(
        "instancer_plugin",
        __name__,
        template_folder="templates",
        static_folder="assets",
    )
    challenge_model = InstancerChallengeModel

    @classmethod
    def calculate_value(cls, challenge):
        solve_count = InstancerChallenge.get_solve_count(challenge)

        # subtract by 1 to give first solver max points
        solve_count = max(solve_count - 1, 0)

        value = float(challenge.initial) * pow(challenge.decay_base, - challenge.decay_factor * solve_count)

        challenge.value = int(value)
        db.session.commit()
        return challenge

    @classmethod
    def create(cls, request):
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
        challenge = InstancerChallengeModel.query.filter_by(
            id=challenge.id).first()
        
        data = super().read(challenge)
        data["initial"] = challenge.initial
        data["decay_base"] = challenge.decay_base
        data["decay_factor"] = challenge.decay_factor
        data["minimum"] = challenge.minimum
        return data

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
        super().update(challenge, request)

        for attr, value in data.items():
            # We need to set these to floats so that the next operations don't operate on strings
            if attr in ("initial", "minimum", "decay_base", "decay_factor"):
                value = float(value)
            setattr(challenge, attr, value)
        return InstancerChallenge.calculate_value(challenge)

    @classmethod
    def get_solve_count(cls, challenge):
        Model = get_model()
        solve_count = (
            Solves.query.join(Model, Solves.account_id == Model.id)
            .filter(
                Solves.challenge_id == challenge.id,
                Model.hidden == False,
                Model.banned == False,
            )
            .count()
        )
        return solve_count

    @classmethod
    def solve(cls, user, team, challenge, request):
        super().solve(user, team, challenge, request)

        # play sound
        # InstancerChallenge.play_sound(user, team, challenge)

        # calculate value
        InstancerChallenge.calculate_value(challenge)
        
