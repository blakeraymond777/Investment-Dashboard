import sys

import db_utils
import finance_utils
import data_scraping_utils

USAGE = """
Usage: python cli.py command [<args>]

  Commands:          Arguments:
  init-db
  portfolio          <user_id>
  add-holding        <user_id> <ticker> <shares>
  delete-portfolio   <user_id>
  set-url            <ticker> <url>
  delete-table       <table_name>
  get-data 
  fetch-nport        <ticker/cik>
  refresh
  exposures          <user_id> <company>/[company ...]
"""

def main():
    args = sys.argv[1:]
    if not args:
        print(USAGE)
        sys.exit(1)

    cmd, rest = args[0], args[1:]

    try:
        if cmd == "init-db":
            db_utils.initialize_tables()

        elif cmd == "portfolio":
            user_id = int(rest[0])
            portfolio = db_utils.load_user_portfolio(user_id)
            if not portfolio:
                print(f"No holdings found for user {user_id}.")
            else:
                print(f"{'Fund':<16} {'Shares':>10}\n")
                print(f"{'-'*16} {'-'*10}")
                for fund, amount in portfolio:
                    print(f"{fund:<16} {amount:>10,}")

        elif cmd == "add-holding":
            user_id, ticker, shares = int(rest[0]), rest[1], int(rest[2])
            db_utils.insert_portfolio_position(ticker, shares, user_id)
            print(f"Added {shares:,} shares of {ticker} to user {user_id}.")

        elif cmd == "delete-portfolio":
            user_id = int(rest[0])
            confirm = input(f"Delete ALL holdings for user {user_id}? [y/N] ").strip().lower()
            if confirm == "y":
                db_utils.delete_user_portfolio(user_id)
                print(f"Deleted all holdings for user {user_id}.")
            else:
                print("Aborted.")

        elif cmd == "delete-table":
            table_name = rest[0]
            db_utils.delete_table(table_name)

        elif cmd == "exposures":
            user_id, companies = int(rest[0]), rest[1:]
            finance_utils.USER = user_id
            if companies: # if blank, use a default test list of companies
                finance_utils.COMPANIES_TO_SEARCH_KEYS = companies
                finance_utils.COMPANIES_TO_SEARCH = dict.fromkeys(companies, 0.0)
            finance_utils.determine_portfolio_exposure()

        elif cmd == "get-data":
            data_scraping_utils.fetch_company_data()
            data_scraping_utils.fetch_fund_data()

        # retrieve nport filing from ticker or CIK
        elif cmd == "fetch-nport":
            fund = rest[0].upper()
            text = data_scraping_utils.fetch_latest_nport_txt(fund)
            if text is None:
                print(f"No N-PORT filing found for {fund}.")
            else:
                out = f"nports/{fund}.txt"
                with open(out, "w", encoding="utf-8") as f:
                    f.write(str(text))
                print(f"Saved: {out}")

        elif cmd == "refresh":
            db_utils.refresh_all_fund_data()

        else:
            print(f"Unknown command: '{cmd}'.{USAGE}")
            sys.exit(1)

    # TODO make error messages more helpful
    except (IndexError, ValueError) as e:
        print(f"Error: {e}")
        #print(f"Invalid arguments for '{cmd}'.{USAGE}")
        sys.exit(1)
    except (TypeError) as e:
        print(f"Error: {e}")
        #print("Could not find composition data for Vanguard or Fidelity funds")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(0)

if __name__ == "__main__":
    main()