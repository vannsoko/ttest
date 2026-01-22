from CTFd.models import db # type: ignore
from CTFd.plugins import register_plugin_assets_directory # type: ignore
from CTFd.plugins.migrations import upgrade # type: ignore
from CTFd.plugins.challenges import CHALLENGE_CLASSES # type: ignore

from .challenge import InstancerChallenge
from .models import create_models
from .util import logger
from .api import page_blueprint

def load(app):
    print("Booting instancer-plugin", flush=True)
    upgrade(plugin_name="instancer_plugin")

    create_models()
    db.session.commit()

    app.register_blueprint(InstancerChallenge.blueprint)
    CHALLENGE_CLASSES["instancer"] = InstancerChallenge
    register_plugin_assets_directory(
        app, base_path=InstancerChallenge.route,
    )

    app.register_blueprint(page_blueprint)

    # register API endpoints
    from . import api

    print("Init finished", flush=True)
