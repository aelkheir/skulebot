from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import Config
from src.models import Base

engine = create_engine(Config.DATABASE_URL)
Session = sessionmaker(engine)


Base.metadata.create_all(engine)
