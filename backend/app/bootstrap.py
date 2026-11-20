from app.db import Base,engine
from app import models
def create_tables():
    """Convenance de développement uniquement; Alembic requis en production."""
    Base.metadata.create_all(bind=engine)
