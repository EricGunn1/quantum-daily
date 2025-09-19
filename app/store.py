from sqlmodel import SQLModel, create_engine

engine = create_engine("sqlite:///quantum_daily.db", echo=False)

def init_db():
    SQLModel.metadata.create_all(engine)
