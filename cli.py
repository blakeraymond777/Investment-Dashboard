import sys

import db_utils
import finance_utils
import data_scraping_utils

USAGE = """
Usage: python cli.py <command> [args]

  init-db
  portfolio        <user_id>
  add-holding      <user_id> <ticker> <shares>
  delete-portfolio <user_id>
  get-url          <ticker>
  set-url          <ticker> <url>
  exposures        <user_id> <company>/[company ...]
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

        elif cmd == "get-url":
            url = db_utils.get_sec_url(rest[0])
            print(url if url else f"No URL found for {rest[0]}.")

        elif cmd == "set-url":
            ticker, url = rest[0], rest[1]
            db_utils.update_existing_fund(ticker, sec_url=url)
            print(f"Updated SEC URL for {ticker}.")

        elif cmd == "delete-table":
            table_name = rest[0]
            db_utils.delete_table(table_name)

        elif cmd == "exposures":
            user_id, companies = int(rest[0]), rest[1:]
            finance_utils.USER = user_id
            finance_utils.COMPANIES_TO_SEARCH_KEYS = companies
            finance_utils.COMPANIES_TO_SEARCH = dict.fromkeys(companies, 0.0)
            finance_utils.determine_portfolio_exposure()

        elif cmd == "get-company-data":
            data_scraping_utils.fetch_company_data()

        elif cmd == "fetch-nport":
            nport = data_scraping_utils.fetch_nport_from_sec_url(rest[0])
            if nport is None:
                print(f"No URL found for {rest[0]}.")
                sys.exit(1)
            print(nport)

        elif cmd == "refresh":
            db_utils.refresh_all_fund_data()

        else:
            print(f"Unknown command: '{cmd}'.{USAGE}")
            sys.exit(1)

    except (IndexError, ValueError):
        print(f"Invalid arguments for '{cmd}'.{USAGE}")
        sys.exit(1)
    except (TypeError):
        print("Could not find composition data for Vanguard or Fidelity funds")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(0)

if __name__ == "__main__":
    main()