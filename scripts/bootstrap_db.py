import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from databases.database_connection import engine
from databases.table_details import Base

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Schema created.")