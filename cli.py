import sys

import data_utils
import run

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
            data_utils.initialize_tables()

        elif cmd == "portfolio":
            user_id = int(rest[0])
            portfolio = data_utils.load_user_portfolio(user_id)
            if not portfolio:
                print(f"No holdings found for user {user_id}.")
            else:
                print(f"\n{'Fund':<16} {'Shares':>10}")
                print(f"{'-'*16} {'-'*10}")
                for fund, amount in portfolio:
                    print(f"{fund:<16} {amount:>10,}")

        elif cmd == "add-holding":
            user_id, ticker, shares = int(rest[0]), rest[1], int(rest[2])
            data_utils.insert_portfolio_position(ticker, shares, user_id)
            print(f"Added {shares:,} shares of {ticker} to user {user_id}.")

        elif cmd == "delete-portfolio":
            user_id = int(rest[0])
            confirm = input(f"Delete ALL holdings for user {user_id}? [y/N] ").strip().lower()
            if confirm == "y":
                data_utils.delete_user_portfolio(user_id)
                print(f"Deleted all holdings for user {user_id}.")
            else:
                print("Aborted.")

        elif cmd == "get-url":
            url = data_utils.get_sec_url(rest[0])
            print(url if url else f"No URL found for {rest[0]}.")

        elif cmd == "set-url":
            ticker, url = rest[0], rest[1]
            data_utils.update_existing_fund(ticker, sec_url=url)
            print(f"Updated SEC URL for {ticker}.")

        # elif cmd == "fetch-nport":
        #     nport = data_utils.fetch_nport_from_sec_url(rest[0])
        #     if nport is None:
        #         print(f"No URL found for {rest[0]}.")
        #         sys.exit(1)
        #     print(nport)

        # elif cmd == "refresh":
        #     days = int(rest[0]) if rest else 7
        #     data_utils.refresh_all_fund_data(max_age_days=days)

        elif cmd == "exposures":
            user_id, companies = int(rest[0]), rest[1:]
            run.USER = user_id
            run.COMPANIES_TO_SEARCH_KEYS = companies
            run.COMPANIES_TO_SEARCH = dict.fromkeys(companies, 0.0)
            run.determine_portfolio_exposure()

        else:
            print(f"Unknown command: '{cmd}'.{USAGE}")
            sys.exit(1)

    except (IndexError, ValueError):
        print(f"Invalid arguments for '{cmd}'.{USAGE}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(0)

if __name__ == "__main__":
    main()