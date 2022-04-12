"""Tools to test databases and tables."""
import psycopg2 as pg
from db_config import config


class DBTester:
    """Test database connection, create table if it does not exist."""

    def __init__(self, table_name: str, sql: str, db_params: dict = None):
        """Initialize db params and run methods as needed."""
        self.db_params = db_params if db_params is not None else config()
        self.test_db_connection()
        if not self.test_table(table_name):
            self.create_table(sql)

    def test_db_connection(self):
        """Test if database connection is doable."""
        conn = pg.connect(**self.db_params)
        return conn

    def test_table(self, table_name: str) -> bool:
        """Test if table exists. Creates it if it does not."""
        with pg.connect(**self.db_params) as conn, conn.cursor() as curs:
            curs.execute(f"""
            SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_name = '{table_name}'
            """)
            table_exists: int = curs.fetchone()[0]
        return True if table_exists else False

    def create_table(self, sql: str) -> None:
        """Create a table with a given SQL."""
        with pg.connect(**self.db_params) as conn, conn.cursor() as curs:
            curs.execute(sql)
            conn.commit()
            curs.execute("SET datestyle = dmy;")
            conn.commit()
