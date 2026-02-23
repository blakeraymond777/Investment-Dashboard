import sqlite3
from datetime import datetime

# Declare class variables

# tickers of funds and corresponding SEC N-PORT filings
# [ fund ticker, sec url ]
FUNDS = {
    "VFIAX": "https://www.sec.gov/Archives/edgar/data/36405/000003640525000125/0000036405-25-000125.txt", # Vanguard 500 Index Fund
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
    "VVIAX": "https://www.sec.gov/Archives/edgar/data/36405/000003640525000234/0000036405-25-000234.txt", # Vanguard Value Index Fund
    "FXAIX": "https://www.sec.gov/Archives/edgar/data/819118/000003540225001329/0000035402-25-001329.txt", # Fidelity 500 Index Fund
    "FSPSX": "https://www.sec.gov/Archives/edgar/data/819118/000003540225001381/0000035402-25-001381.txt" # Fidelity International Index Fund
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

# Helper functions

# create the database if it does not exist and connect it
def connect():
    db_connection = sqlite3.connect("finance_data.db")
    return db_connection

# pull all fund and portfolio information into memory
def load_funds_from_cache(funds_to_get, connection=None):
    if connection is None:
        connection = connect()

    cursor = connection.cursor()

    placeholders = ", ".join("?" * len(funds_to_get))
    cursor.execute(f"SELECT ticker, nport_document FROM funds where ticker in ({placeholders})", funds_to_get)
    
    funds = dict(cursor.fetchall())
    return funds

def load_user_portfolio(user, connection=None):
    if connection is None:
        connection = connect()

    cursor = connection.cursor()

    cursor.execute("SELECT fund, amount FROM portfolios WHERE user = ?", (user,))
    portfolio = cursor.fetchall()

    return portfolio

# create the database tables while not conflicting with existing records
# can be run repeatedly without consequence
def initialize_tables(connection=None):
    if connection is None:
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
    CREATE TABLE IF NOT EXISTS portfolios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fund TEXT NOT NULL,
        amount INTEGER NOT NULL,
        user INTEGER NOT NULL
    )
    """)

    # Insert data
    cursor.executemany("INSERT OR IGNORE INTO funds (ticker, sec_url) VALUES (?, ?)", FUNDS.items())
    cursor.executemany("INSERT OR REPLACE INTO portfolios (fund, amount, user) VALUES (?, ?, ?)", MOCK_PORTFOLIOS)

    print("Successfully freshened database tables")

    connection.commit()
    connection.close()

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
        print("No fields to update.")
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

def delete_table(table, connection=None):
    if connection is None:
        connection = connect()

    cursor = connection.cursor()

    if table is not None:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
        print(f"Successfully deleted table: {table}")
    return

def get_sec_url(fund, connection=None):
    if connection is None:
        connection = connect()

    cursor = connection.cursor()
    cursor.execute("SELECT ticker, sec_url FROM funds WHERE ticker = ?", (fund,))

    url_result = cursor.fetchone()
    if url_result:
        return url_result[1]
    
    return

# delete all holding records for a specific user
def delete_user_portfolio(user, existing_connection=None):
    if user is None:
        raise ValueError("ticker cannot be null")
    
    conn = existing_connection
    if conn is None:
        conn = connect()

    cursor = conn.cursor()
    cursor.execute("DELETE FROM portfolios WHERE ticker = ?", (user,))

    return

# refresh funds database
# pull in data for a fund with a URL that is missing an n-port
# cycle stale records
# def refresh_all_fund_data(connection=None):
#     if connection is None:
#         connection = connect()

#     cursor = connection.cursor()

#     cursor.execute(f"SELECT ticker, nport_document FROM funds where ticker in ({funds})")
#     #cursor.execute(f"SELECT ticker, sec_url FROM funds")
#     funds = list(cursor.fetchall())

#     return

# insert a new record into the portfolio table representing a held position
# def insert_portfolio():
#     return