from CTFd.models import Challenges, Flags, db  # type: ignore
from CTFd.exceptions.challenges import ChallengeCreateException  # type: ignore
from CTFd.plugins import flag_sharing_prot  # type: ignore

from pydantic import BaseModel
from typing import Optional


class InstancerChallengeModel(Challenges):
    __mapper_args__ = {"polymorphic_identity": "instancer"}
    id = db.Column(
        db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )
    short_name = db.Column(db.Text, unique=True, nullable=False)

    def __init__(self, *args, **kwargs):
        super(InstancerChallengeModel, self).__init__(**kwargs)
        try:
            self.value = kwargs["value"]
        except KeyError:
            raise ChallengeCreateException("Missing value for challenge")

def find_chall_short_name(challenge_id: int) -> str | None:
    """ Find the short name for the challenge """
    chall_short_name = db.session.execute(
        db.select(InstancerChallengeModel).filter_by(challenge_id=challenge_id)).first()
    if chall_short_name:
        return chall_short_name.chall_short_name
    return None


class Instances(db.Model):
    __tablename__ = "instances"
    team_id = db.Column(db.Integer, db.ForeignKey(
        "teams.id", ondelete="CASCADE"), primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey(
        "challenges.id", ondelete="CASCADE"), primary_key=True)
    instance_id = db.Column(db.Integer, nullable=False)


def get_instance_id(challenge_id: int, team_id: int) -> int | None:
    """ Get the instance id associated with challenge_id and team_id """
    instance = db.session.execute(db.select(Instances).filter_by(
        challenge_id=challenge_id).filter_by(team_id=team_id)).first()
    if instance is None:
        return None
    return instance.instance_id


def update_instance_id(challenge_id: int, team_id: int, instance_id: int):
    """ Update the instance id associated with challenge_id and team_id """
    instance = db.session.execute(db.select(Instances).filter_by(
        challenge_id=challenge_id).filter_by(team_id=team_id)).first()
    if instance:
        instance.instance_id = instance_id
    else:
        # create new one
        instance = Instances(challenge_id=challenge_id,
                             team_id=team_id, instance_id=instance_id)
        db.session.add(instance)
    db.session.commit()


class InstanceURLs(db.Model):
    __tablename__ = "instance_urls"
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey(
        "teams.id", ondelete="CASCADE"))
    challenge_id = db.Column(db.Integer, db.ForeignKey(
        "challenges.id", ondelete="CASCADE"))
    url = db.Column(db.Text)


def query_instance_urls(challenge_id: int, team_id: int) -> list[str]:
    """ Get a list of all urls for the instance of challenge_id and team_id """
    instance_id = get_instance_id(challenge_id, team_id)
    if instance_id is None:
        return []

    urls = db.session.query(InstanceURLs.url).filter_by(
        team_id=team_id, challenge_id=challenge_id).all()
    # unpack from tuple
    return [url for (url,) in urls]


def add_instance_url(challenge_id: int, team_id: int, url: str):
    """ Inserts an url into InstanceURLs for the instance of challenge_id and team_id. """
    db.session.add(InstanceURLs(
        team_id=team_id, challenge_id=challenge_id, url=url
    ))
    db.session.commit()


def remove_instance_urls(challenge_id: int, team_id: int):
    db.session.query(InstanceURLs).filter(InstanceURLs.team_id == team_id,
                                          InstanceURLs.challenge_id == challenge_id).delete(synchronize_session=False)
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
    flag_obj = Flags.query.filter_by(
        challenge_id=challenge_id,
        type="myflag"
    ).first()
    if flag_obj is None:
        return None
    flag = flag_obj.content
    if flag is None:
        return None

    if flag_obj.type != flag_sharing_prot.SharingProtectedFlag.name:
        return flag

    return flag_sharing_prot.get_team_flag(flag, challenge_id, team_id)


def create_models():
    InstancerChallengeModel.__table__.create(db.engine, checkfirst=True)
    InstanceURLs.__table__.create(db.engine, checkfirst=True)
    Instances.__table__.create(db.engine, checkfirst=True)
