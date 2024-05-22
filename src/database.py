from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import Config
from src.models import Base

engine = create_engine(Config.DATABASE_URL, connect_args={"options": "-c timezone=utc"})
Session = sessionmaker(engine)


Base.metadata.create_all(engine)
