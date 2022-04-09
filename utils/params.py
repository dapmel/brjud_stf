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

# "Incidente" is the primary key because many processes don't have
# "numero_unico"s
sql_stf_data_table = """
    CREATE TABLE IF NOT EXISTS stf_data (
        incidente INTEGER PRIMARY KEY,
        numero_unico TEXT,
        id_stf INTEGER NOT NULL,
        classe_processo_sigla TEXT NOT NULL,
        data_protocolo DATE NOT NULL,
        meio_id SMALLINT NOT NULL,
        tipo_id SMALLINT NOT NULL,
        classe_processo TEXT,
        partes TEXT,
        assuntos TEXT,
        orgao_origem TEXT,
        origem TEXT,
        numeros_origem TEXT,
        scrap_date DATE NOT NULL
    );
"""
sql_stf_data_select_incidents = """SELECT incidente FROM stf_data;"""
sql_stf_data_insert_min = """
    INSERT INTO stf_data (
        incidente, numero_unico, id_stf, classe_processo_sigla, data_protocolo,
        meio_id, tipo_id, scrap_date
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (incidente) DO UPDATE
    SET (scrap_date) = ROW(EXCLUDED.scrap_date);
"""
sql_stf_data_insert_row = """
    INSERT INTO stf_data (
        incidente, numero_unico, id_stf, classe_processo_sigla, data_protocolo,
        meio_id, tipo_id, classe_processo, partes, assuntos, orgao_origem,
        origem, numeros_origem, scrap_date
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (incidente) DO UPDATE
    SET (scrap_date) = ROW(EXCLUDED.scrap_date);
"""
sql_stf_data_select = """SELECT * FROM stf_data;"""
# TODO ON CONFLICT

sql_scrap_log_table = """
    CREATE TABLE IF NOT EXISTS stf_scrap_log (
        classe_processo_sigla TEXT PRIMARY KEY,
        last_id INTEGER NOT NULL,
        scrap_date DATE NOT NULL
    );
"""
sql_scrap_log_select_all = """
    SELECT classe_processo_sigla, last_id FROM stf_scrap_log;
"""
sql_scrap_log_select_highest = """
    SELECT last_id FROM stf_scrap_log ORDER BY last_id DESC LIMIT 1;
"""
sql_scrap_log_select_lowest = """
    SELECT last_id FROM stf_scrap_log ORDER BY last_id ASC LIMIT 1;
"""
sql_scrap_log_select_code = """
    SELECT last_id
        FROM stf_scrap_log
        WHERE classe_processo_sigla = %s
        ORDER BY last_id DESC LIMIT 1;
"""
sql_scrap_log_insert = """
    INSERT INTO stf_scrap_log (
        classe_processo_sigla, last_id, scrap_date
    ) VALUES (%s, %s, %s)
    ON CONFLICT (classe_processo_sigla) DO UPDATE
    SET (last_id) = ROW(EXCLUDED.last_id),
        (scrap_date) = ROW(EXCLUDED.scrap_date)
        WHERE EXCLUDED.last_id > stf_scrap_log.last_id;
"""

# Disabled for now
# # "stf_logs_diaries" table
# sql_log_diaries_table = """
#     CREATE TABLE IF NOT EXISTS stf_logs_diaries (
#         date DATE PRIMARY KEY,
#         scraped BOOLEAN NOT NULL
#     );
# """
# sql_log_diaries_read = """SELECT * FROM stf_logs_diaries ORDER BY date DESC;"""
# sql_log_diaries_read_pending = """
#     SELECT * FROM stf_logs_diaries WHERE scraped = false ORDER BY date DESC;
# """
# sql_log_diaries_add_date = """
#     INSERT INTO stf_logs_diaries (date, scraped) VALUES (%s, %s);
# """
# sql_log_diaries_update_status = """
#     UPDATE stf_logs_diaries SET scraped = %s WHERE date = %s;
# """
