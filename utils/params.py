"""STF Parameters."""
headers = {
    "user-agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
                   "(KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36")
}

# DIARY
diary_root = "https://www.stf.jus.br/portal/diariojusticaeletronico/"
valid_dates_url = diary_root + \
    "montarCalendarioDiarioEletronico.asp?mes={month}&ano={year}"
diary_page = diary_root + \
    "montarDiarioEletronico.asp?tp_pesquisa=0&dataD={date}"
diary_pdf_url = diary_root + "{pdf_uri}"
diary_log_header = ("data", "incidente")
diary_log_path_and_filename = "logs/diarios/{log_date}.csv"

root_url = "http://portal.stf.jus.br/processos/"

# RANGE SEARCH
search_url = root_url + "listarProcessos.asp?classe=&numeroProcesso={num}"
# PROCESS
process_url = root_url + "detalhe.asp?incidente={incidente}"
parties_url = root_url + "abaPartes.asp?incidente={incidente}"
details_url = root_url + "abaInformacoes.asp?incidente={incidente}"

# "stf_data" table
# "Incidente" is the primary key because many processes don't have
# "numero_unico" values
sql_stf_data_create = """
    CREATE TABLE IF NOT EXISTS stf_data (
        incidente INTEGER PRIMARY KEY,
        numero_unico TEXT,
        id_stf INTEGER NOT NULL,
        classe_processo_sigla TEXT NOT NULL,
        data_protocolo DATE NOT NULL,
        meio_id SMALLINT NOT NULL,
        tipo_id SMALLINT NOT NULL,
        classe_processo TEXT NOT NULL,
        partes TEXT,
        assuntos TEXT,
        orgao_origem TEXT,
        origem TEXT,
        numeros_origem TEXT,
        scrap_date DATE NOT NULL
    );
"""
sql_stf_data_insert_row = """
    INSERT INTO stf_data (
        incidente, numero_unico, id_stf, classe_processo_sigla,
        data_protocolo, meio_id, tipo_id, classe_processo, partes,
        assuntos, orgao_origem, origem, numeros_origem, scrap_date
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (incidente) DO UPDATE
    SET (scrap_date) = ROW(EXCLUDED.scrap_date);
"""
sql_stf_data_select = """SELECT * FROM stf_data;"""
# TODO ON CONFLICT

# "stf_logs_diaries" table
sql_log_diaries_table = """
    CREATE TABLE IF NOT EXISTS stf_logs_diaries (
        date DATE PRIMARY KEY,
        scraped BOOLEAN NOT NULL
    );
"""
sql_log_diaries_read = """SELECT * FROM stf_logs_diaries ORDER BY date DESC;"""
sql_log_diaries_read_pending = """
    SELECT * FROM stf_logs_diaries WHERE scraped = false ORDER BY date DESC;
"""
sql_log_diaries_add_date = """
    INSERT INTO stf_logs_diaries (date, scraped) VALUES (%s, %s);
"""
sql_log_diaries_update_status = """
    UPDATE stf_logs_diaries SET scraped = %s WHERE date = %s;
"""

# "stf_logs_searches" table
sql_log_searches_table = """
    CREATE TABLE IF NOT EXISTS stf_logs_searches (
        range_start INTEGER,
        range_end INTEGER,
        scrap_date DATE NOT NULL,
        PRIMARY KEY (range_start, range_end)
    );
"""
sql_log_searches_last_end = """
    SELECT range_end FROM stf_logs_searches ORDER BY range_end DESC LIMIT 1;
"""
sql_log_searches_insert_range = """
    INSERT INTO stf_logs_searches (
        range_start, range_end, scrap_date
    ) VALUES (%s, %s, %s)
    ON CONFLICT (range_start, range_end) DO UPDATE
    SET (scrap_date) = ROW(EXCLUDED.scrap_date);
"""

# "stf_temp_processes_ids" table
sql_temp_processes_ids_create = """
    CREATE TABLE IF NOT EXISTS stf_temp_processes_ids (
        id_stf INT NOT NULL,
        class_id SMALLINT NOT NULL,
        PRIMARY KEY (id_stf, class_id)
    );
"""
sql_temp_processes_ids_read = """
    SELECT * FROM stf_temp_processes_ids;
"""
sql_temp_processes_ids_add_id = """
    INSERT INTO stf_temp_processes_ids (
        id_stf, class_id
    ) VALUES (%s, %s)
    ON CONFLICT (id_stf, class_id) DO NOTHING;
"""
sql_temp_processes_ids_drop_id = """
    DELETE FROM stf_temp_processes_ids
        WHERE id_stf = %s AND class_id = %s;
"""
sql_temp_processes_ids_drop_table = """
    DROP TABLE stf_temp_processes_ids RESTRICT;
"""

# INCIDENTS
sql_temp_incidents_create_table = """
    CREATE TABLE IF NOT EXISTS stf_temp_incidents (
        incident INT PRIMARY KEY,
        id_stf INT
    );
"""
sql_temp_incidents_read = """
    SELECT * FROM stf_temp_incidents;
"""
sql_temp_incidents_insert = """
    INSERT INTO stf_temp_incidents (incident, id_stf) VALUES (%s, %s)
        ON CONFLICT (incident) DO NOTHING;
"""
sql_temp_incidents_remove = """
    DELETE FROM stf_temp_incidents WHERE incident = %s;
"""
sql_temp_incidents_drop_table = """DROP TABLE stf_temp_incidents RESTRICT"""
