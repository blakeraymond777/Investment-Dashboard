from importlib.resources import path
from pathlib import Path
import sqlite3
from datetime import datetime
import csv
import data_scraping_utils

# Declare class variables
_DB_STALE_DAYS = 7

# hard coded dummy data representing portfolios
# [ fund ticker, number of shares, user ]
MOCK_PORTFOLIOS = [
    ["AAA", 15, 1],
    ["VFIAX", 1000, 1], 
    ["FXAIX", 1000, 1], 
    ["TEST2_ordering", 10, 1],
    ["VFIAX", 1000, 1], 
    ["TEST", 1000000, 1],
    ["ACRNX", 10, 1]
]

def _read_csv(path):
    """Read the csv at <path>, skipping the first line of headers and return the data"""
    with path.open("r", newline="") as companies:
        reader = csv.reader(companies)
        next(reader, None)               # skip the first row that has human-readable headers
        return list(reader)

# connect to the database
# create it if it does not exist
def connect():
    db_connection = sqlite3.connect("finance_data.db")
    return db_connection

# pull all fund and portfolio information into memory
# TODO remove this and run single get in a loop?
def load_funds_from_cache(funds_to_get, existing_connection=None):
    conn = existing_connection if existing_connection is not None else connect()
    cursor = conn.cursor()

    placeholders = ", ".join("?" * len(funds_to_get))
    cursor.execute(f"SELECT ticker, nport_document FROM funds where ticker in ({placeholders})", (funds_to_get))
    
    funds = dict(cursor.fetchall())

    if existing_connection is None: conn.close()
    
    return funds

def load_fund(fund, existing_connection=None):    
    conn = existing_connection if existing_connection is not None else connect()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM funds where ticker = ? COLLATE NOCASE", (fund,))
    fund_data = cursor.fetchall()

    # if we had no existing connection to the database, then close the local one we made for this function call
    if existing_connection is None: conn.close()

    return fund_data

# load all portfolio information for a specific user into memory
def load_user_portfolio(user, existing_connection=None):
    conn = existing_connection if existing_connection is not None else connect()
    cursor = conn.cursor()

    cursor.execute("SELECT fund, amount FROM portfolios WHERE user = ?", (user,))
    portfolio = cursor.fetchall()

    if existing_connection is None: conn.close()

    return portfolio

# create the database tables while not conflicting with existing records
# can be run repeatedly without consequence
# use FXAIX and VFIAX (S&P500 index funds) as a base and stitch together (by name/title) more data from the SEC companies list including ticker
def initialize_tables():
    connection = connect()
    cursor = connection.cursor()

    delete_table("portfolios")
    delete_table("companies")

    # Create tables

    # Funds
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS funds (
        ticker TEXT PRIMARY KEY,
        cik TEXT,
        series_id TEXT,
        class_id TEXT,
        nport_document TEXT,
        last_updated TEXT 
    )
    """)

    # Portfolios
    cursor.execute("""
    CREATE TABLE portfolios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fund TEXT NOT NULL,
        amount INTEGER NOT NULL,
        user INTEGER NOT NULL
    )
    """)
    print("Created new portfolios table")

    # Companies
    cursor.execute("""
    CREATE TABLE companies (
        name TEXT PRIMARY KEY,
        title TEXT,
        lei TEXT,
        cusip TEXT,
        ticker TEXT,
        cik TEXT          
    )
    """)
    print("Created new companies table")

    # read data in from csv representing company scrape
    if not data_scraping_utils.SCRAPED_COMPANY_DATA_CSV.is_file():
        print(f"CSV file did not exist ({data_scraping_utils.SCRAPED_COMPANY_DATA_CSV}), creating and populating it")
        data_scraping_utils.fetch_company_data()
    company_data = _read_csv(data_scraping_utils.SCRAPED_COMPANY_DATA_CSV)

    if not data_scraping_utils.SCRAPED_FUND_DATA_CSV.is_file():
        print(f"CSV file did not exist ({data_scraping_utils.SCRAPED_FUND_DATA_CSV}), creating and populating it")
        data_scraping_utils.fetch_fund_data()
    fund_data = _read_csv(data_scraping_utils.SCRAPED_FUND_DATA_CSV)

    # insert data
    cursor.executemany("INSERT OR IGNORE INTO funds (ticker, cik, series_id, class_id) VALUES (?, ?, ?, ?)", fund_data)
    cursor.executemany("INSERT OR REPLACE INTO portfolios (fund, amount, user) VALUES (?, ?, ?)", MOCK_PORTFOLIOS)
    cursor.executemany("INSERT OR REPLACE INTO companies (name, title, lei, cusip, ticker, cik) VALUES (?, ?, ?, ?, ?, ?)", company_data)

    connection.commit()
    connection.close()

    print("\nSuccessfully refreshed database tables: funds, portfolios, companies\n")
    return

# insert a new record into the fund table representing a new fund
def update_existing_fund(ticker, nport_document, existing_connection=None):
    if ticker is None:
        raise ValueError("ticker cannot be null")

    if nport_document is None:
        raise ValueError("nport_document cannot be null")

    conn = existing_connection if existing_connection is not None else connect()
    cursor = conn.cursor()

    cursor.execute("UPDATE funds SET nport_document = ?, last_updated = ? WHERE ticker = ?", (nport_document, datetime.now().isoformat(), ticker))
    conn.commit()

    # if we had no existing connection to the database, then close the local one we made for this function call
    if existing_connection is None: conn.close()

    return

def delete_table(table, existing_connection=None):
    conn = existing_connection if existing_connection is not None else connect()
    cursor = conn.cursor()

    if table is not None:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
        print(f"Successfully deleted table: {table}")

    # if we had no existing connection to the database, then close the local one we made for this function call
    if existing_connection is None: conn.close()

    return

# delete all holding records for a specific user
def delete_user_portfolio(user, existing_connection=None):
    if user is None:
        raise ValueError("ticker cannot be null")
    
    conn = existing_connection if existing_connection is not None else connect()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM portfolios WHERE user = ?", (user,))

    # if we had no existing connection to the database, then close the local one we made for this function call
    if existing_connection is None: conn.close()

    return

# insert a new record into the portfolio table representing a held position
def insert_portfolio_position(fund, amount, user, existing_connection=None):
    if fund is None:
        raise ValueError("fund cannot be null")
    if amount is None:
        raise ValueError("amount cannot be null")
    if user is None:
        raise ValueError("user cannot be null")

    conn = existing_connection if existing_connection is not None else connect()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO portfolios (fund, amount, user) VALUES (?, ?, ?)",
        (fund, amount, user)
    )
    conn.commit()

    if existing_connection is None: conn.close()

    return

# determine stale funds to update (from passed in or all)
# loop through and get NPORTs for each
# update database table
# TODO test if this still works as intended
def refresh_all_fund_data(existing_connection=None):
    conn = existing_connection if existing_connection is not None else connect()
    cursor = conn.cursor()

    cursor.execute("SELECT ticker FROM funds WHERE (nport_document IS NULL OR nport_document = '' AND sec_url IS NOT NULL) OR last_updated IS NULL OR last_updated < datetime('now', ?)", (f"-{_DB_STALE_DAYS} days",))
    stale_fund_tickers = cursor.fetchall()

    if not stale_fund_tickers:
        print("No stale database records found")
    else:
        stale_funds_updated = []
        for (fund,) in stale_fund_tickers:
            new_nport = data_scraping_utils.fetch_latest_nport_txt(fund)
            if new_nport:
                stale_funds_updated.append(fund)
                update_existing_fund(fund, new_nport, conn)
        print(f"Updated stale funds in the database: {stale_funds_updated}")

    if existing_connection is None: conn.close()
    
    return