import sqlite3
from datetime import datetime
import csv
import data_scraping_utils

# Declare class variables

DB_STALE_DAYS = 7

# tickers of funds and corresponding SEC N-PORT filings
# [ fund ticker, sec url ]
FUNDS = {
    "VFIAX": "https://www.sec.gov/Archives/edgar/data/36405/000003640525000125/0000036405-25-000125.txt", # Vanguard 500 Index Fund
    "FXAIX": "https://www.sec.gov/Archives/edgar/data/819118/000003540225001329/0000035402-25-001329.txt", # Fidelity 500 Index Fund
    "QQQ": "https://www.sec.gov/Archives/edgar/data/1067839/000106783925000007/0001067839-25-000007.txt", # Invesco QQQ Trust
    "VMVIX": "https://www.sec.gov/Archives/edgar/data/36405/000003640525000245/0000036405-25-000245.txt", # Vanguard Mid-cap Value Fund
    "VIEIX": "https://www.sec.gov/Archives/edgar/data/36405/000003640525000243/0000036405-25-000243.txt", # Vanguard Extended Market Index Fund
    "VIGIX": "https://www.sec.gov/Archives/edgar/data/36405/000003640525000244/0000036405-25-000244.txt", # Vanguard Growth Index Fund
    "VSCIX": "https://www.sec.gov/Archives/edgar/data/36405/000003640525000242/0000036405-25-000242.txt", # Vanguard Small-Cap Index Fund
    "VV": "https://www.sec.gov/Archives/edgar/data/36405/000003640525000241/0000036405-25-000241.txt", # Vanguard Large-Cap Index Fund
    "VBR": "https://www.sec.gov/Archives/edgar/data/36405/000003640525000240/0000036405-25-000240.txt", # Vanguard Small-Cap Value Index Fund (ETF)
    "VSIAX": "https://www.sec.gov/Archives/edgar/data/36405/000003640525000240/0000036405-25-000240.txt", # REMEMBER TO UPDATE ALL LIKE THIS # Vanguard Small-Cap Value Index Fund (Admiral Shares)
    "VOT": "https://www.sec.gov/Archives/edgar/data/36405/000003640525000239/0000036405-25-000239.txt", # Vanguard Mid-Cap Growth Index Fund
    "VMGMX": "https://www.sec.gov/Archives/edgar/data/36405/000003640525000239/0000036405-25-000239.txt", # Vanguard Mid-Cap Growth Index Fund
    "VO": "https://www.sec.gov/Archives/edgar/data/36405/000003640525000236/0000036405-25-000236.txt", # Vanguard Mid-Cap Index Fund
    "VIMAX": "https://www.sec.gov/Archives/edgar/data/36405/000003640525000236/0000036405-25-000236.txt", # Vanguard Mid-Cap Index Fund
    "VTI": "https://www.sec.gov/Archives/edgar/data/36405/000003640525000235/0000036405-25-000235.txt", # Vanguard Total Stock Market Index Fund
    "VTSAX": "https://www.sec.gov/Archives/edgar/data/36405/000003640525000235/0000036405-25-000235.txt", # Vanguard Total Stock Market Index Fund
    "VTV": "https://www.sec.gov/Archives/edgar/data/36405/000003640525000234/0000036405-25-000234.txt", # Vanguard Value Index Fund
    "VVIAX": "https://www.sec.gov/Archives/edgar/data/36405/000003640525000234/0000036405-25-000234.txt", # Vanguard Value Index Fund    "FSPSX": "https://www.sec.gov/Archives/edgar/data/819118/000003540225001381/0000035402-25-001381.txt" # Fidelity International Index Fund
}

# hard coded dummy data representing portfolios
# [ fund ticker, number of shares, user ]
MOCK_PORTFOLIOS = [
    ["AAA", 15, 1],
    ["VFIAX", 1000, 1], 
    ["FXAIX", 1000, 1], 
    ["TEST2_ordering", 10, 1],
    ["VFIAX", 1000, 1], 
    ["TEST", 1000000, 1]
]


# create the database if it does not exist and connect it
def connect():
    db_connection = sqlite3.connect("finance_data.db")
    return db_connection

# pull all fund and portfolio information into memory
def load_funds_from_cache(funds_to_get, existing_connection=None):
    conn = existing_connection
    if conn is None:
        conn = connect()

    cursor = conn.cursor()

    placeholders = ", ".join("?" * len(funds_to_get))
    cursor.execute(f"SELECT ticker, nport_document FROM funds where ticker in ({placeholders})", funds_to_get)
    
    funds = dict(cursor.fetchall())

    if existing_connection is None:
        conn.close()
    
    return funds

def load_user_portfolio(user, existing_connection=None):
    conn = existing_connection
    if conn is None:
        conn = connect()

    cursor = conn.cursor()

    cursor.execute("SELECT fund, amount FROM portfolios WHERE user = ?", (user,))
    portfolio = cursor.fetchall()

    if existing_connection is None:
        conn.close()

    return portfolio

# create the database tables while not conflicting with existing records
# can be run repeatedly without consequence
def initialize_tables():
    connection = connect()
    cursor = connection.cursor()

    delete_table("portfolios")

    # Create tables

    # Funds
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS funds (
        ticker TEXT PRIMARY KEY,
        sec_url TEXT,
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
    CREATE TABLE IF NOT EXISTS companies (
        name TEXT PRIMARY KEY,
        title TEXT,
        lei TEXT,
        cusip TEXT,
        ticker TEXT,
        cik TEXT          
    )
    """)

    # read data in from csv representing company scrape
    with open("scraped_companies.csv", "r") as f:
        reader = csv.reader(f)
        company_data = [row for row in reader]

    # Insert data
    cursor.executemany("INSERT OR IGNORE INTO funds (ticker, sec_url) VALUES (?, ?)", FUNDS.items())
    cursor.executemany("INSERT OR REPLACE INTO portfolios (fund, amount, user) VALUES (?, ?, ?)", MOCK_PORTFOLIOS)
    cursor.executemany("INSERT OR REPLACE INTO companies (name, title, lei, cusip, ticker, cik) VALUES (?, ?, ?, ?, ?, ?)", company_data)

    print("Successfully refreshed database tables: funds, portfolios, companies")

    connection.commit()
    connection.close()
    return

# insert a new record into the fund table representing a new fund
def update_existing_fund(ticker, sec_url=None, nport_document=None, existing_connection=None):
    if ticker is None:
        raise ValueError("ticker cannot be null")
    
    conn = existing_connection
    if conn is None:
        conn = connect()

    cursor = conn.cursor()

    fields = {"sec_url": sec_url, "nport_document": nport_document}
    updates = {k: v for k, v in fields.items() if v is not None}

    if not updates:
        print(f"No fields to update for {ticker}.")
        return
    
    updates["last_updated"] = datetime.now().isoformat()

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    query = f"UPDATE funds SET {set_clause} WHERE ticker = ?"

    values = list(updates.values()) + [ticker]

    cursor.execute(query, values)
    conn.commit()

    # if we had no existing connection to the database, then close the local one we made for this function call
    if existing_connection is None:
        conn.close()

    return

def delete_table(table, existing_connection=None):
    conn = existing_connection
    if conn is None:
        conn = connect()

    cursor = conn.cursor()

    if table is not None:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
        print(f"Successfully deleted table: {table}")

    # if we had no existing connection to the database, then close the local one we made for this function call
    if existing_connection is None:
        conn.close()

    return

def get_sec_url(fund, existing_connection=None):
    conn = existing_connection
    if conn is None:
        conn = connect()

    cursor = conn.cursor()
    
    cursor.execute("SELECT ticker, sec_url FROM funds WHERE ticker = ?", (fund,))

    url_result = cursor.fetchone()
    if url_result:
        return url_result[1]
    
    # if we had no existing connection to the database, then close the local one we made for this function call
    if existing_connection is None:
        conn.close()

    return

# delete all holding records for a specific user
def delete_user_portfolio(user, existing_connection=None):
    if user is None:
        raise ValueError("ticker cannot be null")
    
    conn = existing_connection
    if conn is None:
        conn = connect()

    cursor = conn.cursor()
    cursor.execute("DELETE FROM portfolios WHERE user = ?", (user,))

    # if we had no existing connection to the database, then close the local one we made for this function call
    if existing_connection is None:
        conn.close()

    return

# insert a new record into the portfolio table representing a held position
def insert_portfolio_position(fund, amount, user, existing_connection=None):
    if fund is None:
        raise ValueError("fund cannot be null")
    if amount is None:
        raise ValueError("amount cannot be null")
    if user is None:
        raise ValueError("user cannot be null")

    conn = existing_connection
    if conn is None:
        conn = connect()

    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO portfolios (fund, amount, user) VALUES (?, ?, ?)",
        (fund, amount, user)
    )
    conn.commit()

    if existing_connection is None:
        conn.close()

    return

# determine stale funds to update (from passed in or all)
# loop through and get NPORTs for each
# update database table
def refresh_all_fund_data(existing_connection=None):
    conn = existing_connection
    if conn is None:
        conn = connect()

    cursor = conn.cursor()

    cursor.execute("SELECT ticker FROM funds WHERE (nport_document IS NULL OR nport_document = '' AND sec_url IS NOT NULL) OR last_updated IS NULL OR last_updated < datetime('now', ?)", (f"-{DB_STALE_DAYS} days",))
    stale_fund_tickers = cursor.fetchall()

    stale_funds_updated = []

    if not stale_fund_tickers:
        print("No stale database records found")
    else:
        for (fund,) in stale_fund_tickers:
            new_nport = data_scraping_utils.fetch_nport_from_sec_url(fund)
            if new_nport:
                stale_funds_updated.append(fund)
                update_existing_fund(fund, None, new_nport, conn)
        print(f"Updated stale funds in the database: {stale_funds_updated}")

    if existing_connection is None:
        conn.close()
    
    return


