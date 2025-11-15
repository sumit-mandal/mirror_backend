from databases.database_connection import engine
from databases.table_details import Base

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Schema created.")