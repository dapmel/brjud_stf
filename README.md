[![codecov](https://codecov.io/gh/tohwiket/brjud_stf/branch/main/graph/badge.svg?token=TJ5KB97LTG)](https://codecov.io/gh/tohwiket/brjud_stf)
![example workflow](https://github.com/tohwiket/brjud_stf/actions/workflows/stf.yml/badge.svg)

# STF scrapper

Automatically scraps the API that feeds the [Supremo Tribunal Federal Search](https://portal.stf.jus.br/).

The scraping is divided in two steps:

1. Retrieval of valid "incidentes" and scraping of minimal processes data through multiple STF searches
2. Scraping of some of the detailed data of each valid process

## Requirements
This program needs a functionining Postgresql database to work. The database configuration parameters must be included in the `db\database.yml` file.

### Install required packages
```
python3 -m pip install -r requirements.txt
```
### Test your copy
```
python3 -m pytest --cov=./ --cov-config .coveragerc
```

### Sample usage: Full run
```
# Scrap all processes
search_scraper = SearchScraper()
process_scraper = ProcessScraper()
status = True
while status:
    # 'max', 'min' and 'code' modes available. Check docstrings.
    status = search_scraper.start(mode="max")
    process_scraper.start()
```

## Caution!
Always mind your disk space! The sample code above can and will fill your storage with very large ammounts of data.
