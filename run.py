import re
import data_utils
import time
from threading import Thread, Lock

# Declare class variables
# static globals
USER = 1
START_TIME = END_TIME = None
# FUNDS should be a dictionary with the fund ticker and the nport
FUNDS = {}

LOCK = Lock()

COMPANIES_TO_SEARCH_KEYS = ["Amazon.com Inc", "Another NA Company", "Netflix", "NA-Company!"]
#COMPANIES_TO_SEARCH = dict.fromkeys(COMPANIES_TO_SEARCH_KEYS, 0.0)
COMPANIES_TO_SEARCH = dict.fromkeys(COMPANIES_TO_SEARCH_KEYS, 0.0)

# use fund report filing to determine percentage weights of various company holdings and update cumulative portfolio table
def calculate_company_exposures_for_fund(fund, num_shares):
    # 0 --> no key was found in database
    # None --> key found in database but no or stale nport_document value
    # Value --> nport_document exists
    nport = FUNDS.get(fund, 0)
    match nport:
        case 0:
            print(f"Fund not found in database: {fund}")
            return
        case None:
            nport = data_utils.fetch_nport_from_sec_url(fund)
            if nport is None:
                print(f"Could not find an N-PORT filing for fund: {fund}. It will not be calculated in the results")
                return
            else:
                # update the existing record because we fetched a new document
                print(f"updating cached nport document for database entry of fund {fund}")
                data_utils.update_existing_fund(fund, None, nport)
        case _:
            print(f"Using cached nport document for fund {fund}!")
             
    # Parse all holdings of the fund into iterable sections
    fund_investments = re.findall(r'<invstOrSec>.*?</invstOrSec>', nport, re.DOTALL)

    # loop through all fund_positions and check for each companie to search
    for fund_position in fund_investments:
        for company in COMPANIES_TO_SEARCH_KEYS:
            # [MVP]: search for just the "name" (ex: "Amazon.com Inc) within the report filing
            name_match = re.search(re.escape(company), fund_position, re.IGNORECASE)
        
            # Get percentage weight if holding for company is found
            if name_match:
                holding_percentage = re.search(r'<pctVal>(.*?)</pctVal>', fund_position)

                # Determine user value of certain holding (NAV * num shares held) and holding of lookup stock (weight % of lookup * num shares held)
                if holding_percentage:
                    company_holding_amount = float(holding_percentage.group(1)) * num_shares
                    with LOCK:
                        print(f"Holding ${company_holding_amount} of {company} in {fund}")
                        COMPANIES_TO_SEARCH[company] = COMPANIES_TO_SEARCH.get(company, 0.0) + company_holding_amount
        
    return

# manage program timer
def timer():
    global START_TIME, END_TIME
    if START_TIME is None:
        START_TIME = time.perf_counter()
    else:
        END_TIME = time.perf_counter()
    return

# nicely print results
def print_exposures():
    print("\n\n---------------------------------------")
    print("| Companies with Calculated Exposures |")
    print("---------------------------------------")
    for company, amount in COMPANIES_TO_SEARCH.items():
        print(f"{company} --> {"no exposure found" if amount == 0.0 else f"${amount}"}")
    print("---------------------------------------")
    return

def determine_portfolio_exposure():
    global FUNDS, COMPANIES_TO_SEARCH

    db_connection = data_utils.connect()

    PORTFOLIO = data_utils.load_user_portfolio(USER, db_connection)
    PORTFOLIO_FLATTENED = {}

    # flatten portfolio into dictionary of unique funds (consolidated) and cumulative number of shares held of each
    for fund, num_shares in PORTFOLIO:
        PORTFOLIO_FLATTENED[fund] = PORTFOLIO_FLATTENED.get(fund, 0) + num_shares

    print(f"(User {USER}) flattened portfolio to calculate exposures for: {PORTFOLIO_FLATTENED}")
    print(f"Companies to check exposures to: {COMPANIES_TO_SEARCH_KEYS}\n")

    FUNDS = data_utils.load_funds_from_cache(list(PORTFOLIO_FLATTENED.keys()), db_connection)

    # loop through dictionary of positions and lookup each COMPANY_TO_SEARCH dictionary value into that fund and update cumulative total holding
    # for searching, use legal name for now, but can also use: LEI, ISIN, FIGI
    threads = []
    for fund, num_shares in PORTFOLIO_FLATTENED.items():
        t = Thread(target=calculate_company_exposures_for_fund, args=(fund, num_shares))
        t.start()
        threads.append(t)

    [t.join() for t in threads]

    # round values in place within dictionary to cents
    COMPANIES_TO_SEARCH = {holding: round(amount, 2) for holding, amount in COMPANIES_TO_SEARCH.items()}
    print_exposures()

    db_connection.close()
    
    return

def main():
    timer()

    # for now, just run a single function, but use modularity to decide which to use as features are added
    determine_portfolio_exposure()

    timer()
    if START_TIME and END_TIME is not None:
        elapsed_time = END_TIME - START_TIME
        print(f"\nExecution time: {elapsed_time:.4f} seconds\n")

if __name__ == "__main__":
    main()