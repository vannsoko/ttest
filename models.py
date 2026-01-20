from CTFd.models import Challenges, Flags, db  # type: ignore
from CTFd.exceptions.challenges import ChallengeCreateException  # type: ignore
from CTFd.plugins import flag_sharing_prot  # type: ignore

from pydantic import BaseModel
from typing import Optional

DEFAULT_INSTANCE_ID = 1


class InstancerChallengeModel(Challenges):
    __mapper_args__ = {"polymorphic_identity": "instancer"}
    id = db.Column(
        db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )
    short_name = db.Column(db.Text, unique=True, nullable=False)
    initial = db.Column(db.Integer, default=0)
    minimum = db.Column(db.Integer, default=0)
    decay_base = db.Column(db.Float, default=0.)
    decay_factor = db.Column(db.Float, default=0.)
    needs_deployment = db.Column(db.Boolean, default=True)

    def __init__(self, *args, **kwargs):
        try:
            kwargs.update({"value": kwargs["initial"]})
        except KeyError:
            raise ChallengeCreateException(
                "Missing initial value for challenge")
        super(InstancerChallengeModel, self).__init__(**kwargs)
        self.value = kwargs["value"]


def get_chal(challenge_id: int) -> InstancerChallengeModel:
    return db.session.get(InstancerChallengeModel, challenge_id)


def find_chall_short_name(challenge_id: int) -> str | None:
    """ Find the short name for the challenge """
    chall = db.session.query(InstancerChallengeModel).filter_by(
        id=challenge_id).first()
    if chall:
        return chall.short_name
    return None


class Instances(db.Model):
    __tablename__ = "instances"
    team_id = db.Column(db.Integer, db.ForeignKey(
        "teams.id", ondelete="CASCADE"), primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey(
        "challenges.id", ondelete="CASCADE"), primary_key=True)
    instance_id = db.Column(db.Integer, nullable=False)


def get_instance_id(challenge_id: int, team_id: int) -> int:
    """ Get the instance id associated with challenge_id and team_id """
    instance = db.session.query(Instances).filter_by(
        challenge_id=challenge_id, team_id=team_id).first()
    if instance is None:
        update_instance_id(challenge_id, team_id, DEFAULT_INSTANCE_ID)
        return DEFAULT_INSTANCE_ID
    return instance.instance_id


def update_instance_id(challenge_id: int, team_id: int, instance_id: int = DEFAULT_INSTANCE_ID):
    """ Update the instance id associated with challenge_id and team_id """
    instance = db.session.query(Instances).filter_by(
        challenge_id=challenge_id, team_id=team_id).first()
    if instance:
        instance.instance_id = instance_id
    else:
        # create new one
        instance = Instances(challenge_id=challenge_id,
                             team_id=team_id, instance_id=instance_id)
        db.session.add(instance)
    db.session.commit()

# Note: CTFd requires pydantic v1, this model should be compatible


class DeployedPort(BaseModel):
    class Config:
        extra = 'forbid'

    name: str
    display: bool
    type: str
    description: Optional[str] = None
    hostname: str
    port: int
    ssl: bool


def get_team_flag(challenge_id: int, team_id: int) -> str | None:
    # CAUTION: We do not support challenges with multiple flags
    flag_obj = Flags.query.filter_by(challenge_id=challenge_id).first()
    if flag_obj is None:
        return None
    flag = flag_obj.content
    if flag is None:
        return None

    if flag_obj.type != flag_sharing_prot.SharingProtectedFlag.name:
        return flag

    return flag_sharing_prot.get_team_flag(flag, team_id, challenge_id)


def create_models():
    InstancerChallengeModel.__table__.create(db.engine, checkfirst=True)
    Instances.__table__.create(db.engine, checkfirst=True)
