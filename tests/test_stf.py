"""STF tests."""
from datetime import date, datetime
from typing import List
import psycopg2 as pg
import pytest

import STF
import utils.params as stf_params

from db_utils.db_testing import db_testing

# Parameters of the test database
db_params = {
    "host": "localhost",
    "database": "jusdata_test",
    "user": "postgres",
    "password": "postgres"
}

sql_drop_all_tables = """
    DO $$ DECLARE
    r RECORD;
    BEGIN
    FOR r IN (SELECT tablename FROM pg_tables
        WHERE schemaname = current_schema()) LOOP
        EXECUTE 'DROP TABLE ' || quote_ident(r.tablename) || ' CASCADE';
    END LOOP;
    END $$;
"""


class TestSTFSearchScraper:
    """Test STF Search Scraper."""

    today_date: date = datetime.today().date()

    def test_database_and_search_log_table(self):
        """Test database availability and existence/creation of log table.

        Other tests will create tables as well. This test simply allows
        detailed testing of the general table creation mechanism if needed.
        """
        assert pg.connect(**db_params)

        with pg.connect(**db_params) as conn, conn.cursor() as curs:
            # Drop all existing tables
            curs.execute(sql_drop_all_tables)
            conn.commit()

            # Create ``stf_temp_incidents`` table
            db_testing(
                "stf_temp_incidents",
                stf_params.sql_temp_incidents_create_table, db_params)

            # Test if table now exists
            curs.execute("""
                SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_name = 'stf_temp_incidents';
                """)
            assert curs.fetchone()[0]

    def test_search_scraper(self):
        """Test STF search scraper."""
        scraper = STF.SearchScraper(db_params)
        scraper.range_size = 1

        # The start method returns True on successes
        status: bool = scraper.start()
        assert status

    def test_search_logs(self):
        """Check integrity of data in ``stf_logs_searches`` table."""
        sql_log_searches: str = """SELECT * FROM stf_logs_searches;"""

        # Check log format and size
        with pg.connect(**db_params) as conn, conn.cursor() as curs:
            curs.execute(sql_log_searches)
            # Assert only one range was created
            scrap_ranges: tuple = curs.fetchall()
            assert len(scrap_ranges) == 1

            scrap_range: tuple = scrap_ranges[0]
            range_start, range_end, scrap_date = scrap_range
            # Check if range and scrap date were correct
            assert range_start == 1
            assert range_end == 2
            assert scrap_date == self.today_date

        # Check update of scrap_date
        test_scrap_date: date = datetime(2030, 3, 3).date()
        with pg.connect(**db_params) as conn, conn.cursor() as curs:
            test_payload: tuple = (1, 2, test_scrap_date)
            curs.execute(
                stf_params.sql_log_searches_insert_range, test_payload)
            conn.commit()
            # Another "SELECT" is needed because "RETURNING" is not recomended
            # on upsert operations: https://stackoverflow.com/a/42217872
            curs.execute(sql_log_searches)
            scrap_range: tuple = curs.fetchone()
            # Check if new date is correct
            assert scrap_range[2] == test_scrap_date

    @pytest.mark.skip(reason="STF is blocking requests made from Github")
    def test_processes_data(self):
        """Check integrity of data in ``stf_temp_incidents`` table."""
        with pg.connect(**db_params) as conn, conn.cursor() as curs:
            curs.execute(stf_params.sql_temp_incidents_read)
            data_rows: List(tuple) = curs.fetchall()
            # Assert that all 42 incidents with `id_stf` = 1 are scraped
            assert len(data_rows) == 42


class TestSTFProcessScraper:
    """Test STF proccess scraper."""

    def test_db_and_table(self):
        """Reset database, create log table and insert test value."""
        with pg.connect(**db_params) as conn, conn.cursor() as curs:
            # Drop all existing tables
            curs.execute(sql_drop_all_tables)
            conn.commit()

            # Create ``stf_temp_incidents`` table
            db_testing(
                "stf_temp_incidents",
                stf_params.sql_temp_incidents_create_table, db_params)

            # Insertion of valid incident for testing
            curs.execute(stf_params.sql_temp_incidents_insert, (1428339,))

    @pytest.mark.skip(reason="STF is blocking requests made from Github")
    def test_details_scraping(self):
        """Test quality of scraping."""
        scraper = STF.ProcessScraper(db_params)
        status: bool = scraper.start()
        assert status

        with pg.connect(**db_params) as conn, conn.cursor() as curs:
            curs.execute(stf_params.sql_stf_data_select)
            data = curs.fetchall()

        # Only one incident must have been scraped
        assert len(data) == 1

        # Assert the correct incident was scraped
        assert data[0][0] == 1428339
