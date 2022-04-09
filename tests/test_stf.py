"""STF tests."""
from datetime import date, datetime
from typing import List
import psycopg2 as pg
import pytest

import STF
import utils.params as params

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
                "stf_data", params.sql_stf_data_table, db_params)
            db_testing("stf_scrap_log", params.sql_scrap_log_table, db_params)
            # Test if table now exists
            curs.execute("""
                SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_name = 'stf_data';
                """)
            assert curs.fetchone()[0]
            curs.execute("""
                SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_name = 'stf_scrap_log';
                """)
            assert curs.fetchone()[0]

    def test_search_scraper(self):
        """Test STF search scraper."""
        scraper = STF.SearchScraper(db_params)
        # step = 1 would generate errors as the starting id would always be
        # the same as the last id scraped
        scraper.step = 2

        # The start method returns True on successes
        status: bool = scraper.start(mode="max")
        assert status

    def test_search_logs(self):
        """Check integrity of data in ``stf_scrap_log`` table."""
        with pg.connect(**db_params) as conn, conn.cursor() as curs:
            curs.execute(params.sql_scrap_log_select_all)
            data = curs.fetchall()
            assert len(data) == 46

    def test_processes_data(self):
        """Check integrity of data in ``stf_data`` table."""
        with pg.connect(**db_params) as conn, conn.cursor() as curs:
            curs.execute(params.sql_stf_data_select_incidents)
            data_rows: List(tuple) = curs.fetchall()
            assert len(data_rows) == 78


@pytest.mark.skip(reason="To be updated.")
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
