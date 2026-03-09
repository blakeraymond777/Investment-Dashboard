import requests
import os
import re
import csv
import json
import db_utils
from dotenv import load_dotenv

# determine the sec url to use for the fund by checking local and then programmatically searching EDGAR if needed
# [MVP]: lookup into dictionary/database, no handling if fund not found
def fetch_nport_from_sec_url(fund_ticker):
    load_dotenv()
    email = os.getenv("USER_AGENT_EMAIL")

    # check if we have a url already but are just missing the nport
    url = db_utils.get_sec_url(fund_ticker)
    if url is None:
        print(f"No SEC url to check for {fund_ticker}")
        return None

    # Fetch the file
    headers = {"User-Agent": f"PersonalInvestmentApp {email}"}
    response = requests.get(url, headers=headers)
    
    return response.text

def fetch_data_to_populate_companies(url):
    load_dotenv()
    email = os.getenv("USER_AGENT_EMAIL")

    # Fetch the file
    headers = {"User-Agent": f"PersonalInvestmentApp {email}"}
    response = requests.get(url, headers=headers)
    data = response.text

    # Check if we are looking at an NPORT doc
    fund_investments = re.findall(r'<invstOrSec>.*?</invstOrSec>', data, re.DOTALL)

    # Otherwise, we are looking at the company tickers JSON, so return it unfiltered
    if fund_investments == []:
        return data

    # [ name, title, lei, cusip ]
    all_funds = []
    for fund_position in fund_investments:
        this_fund = []

        name = re.search(r'<name>(.*?)</name>', fund_position)
        if name: 
            if name.group(1) == 'N/A': continue
            this_fund.append(name.group(1))

        title = re.search(r'<title>(.*?)</title>', fund_position)
        if title: this_fund.append(title.group(1))

        lei = re.search(r'<lei>(.*?)</lei>', fund_position)
        if lei: this_fund.append(lei.group(1))

        cusip = re.search(r'<cusip>(.*?)</cusip>', fund_position)
        if cusip: this_fund.append(cusip.group(1))

        all_funds.append(this_fund)

    return all_funds

def fetch_company_data():
        # Vanguard - VFIAX
        url_vanguard = "https://www.sec.gov/Archives/edgar/data/36405/000003640526000063/0000036405-26-000063.txt"

        # Fidelity - FXAIX
        url_fidelity = "https://www.sec.gov/Archives/edgar/data/819118/000003540225001329/0000035402-25-001329.txt"

        # SEC-registered companies with tickers/CIKs
        url_companies = "https://www.sec.gov/files/company_tickers.json"

        # Load fund composition data
        all_vanguard_fund_companies = fetch_data_to_populate_companies(url_vanguard)
        all_fidelity_fund_companies = fetch_data_to_populate_companies(url_fidelity)

        # Start with list of companies in fidelity fund and merge in new values from vanguard's fund
        # These lists should be almost identical (they are both tracking the S&P 500)
        if all_fidelity_fund_companies:
            merged_companies = list(all_fidelity_fund_companies).copy()
            if all_vanguard_fund_companies:
                for v_fund in all_vanguard_fund_companies:
                    overlap_flag = False
                    for f_fund in all_fidelity_fund_companies:
                        # Match names/titles to each other or leis
                        if (v_fund[0].casefold() == f_fund[0].casefold() or
                            v_fund[0].casefold() == f_fund[1].casefold() or
                            v_fund[1].casefold() == f_fund[1].casefold() or
                            v_fund[1].casefold() == f_fund[0].casefold() or
                            (len(v_fund) > 2 and len(f_fund) > 2) or v_fund[3] == f_fund[3] ): 
                                overlap_flag = True
                                break
                    # Found a company in the Vanguard fund that was not in the Fidelity fund
                    if not overlap_flag:
                        merged_companies.append(v_fund)
        else: 
            merged_companies = list(all_vanguard_fund_companies).copy()

        print(f"Found {len(merged_companies)} companies within Vanguard/Fidelity S&P500 funds\n")
        # filter out "N/A" values - use empty string "" instead
        merged_companies = [["" if item == "N/A" else item for item in row] for row in merged_companies]

        # Scrape a large list of SEC-registered companies and their tickers/CIK values and parse into JSON
        company_scraped_data = fetch_data_to_populate_companies(url_companies)
        if company_scraped_data:
            all_companies = json.loads(str(company_scraped_data))

            match_count = 0
            for company in merged_companies:
                # sanitize name and title for the sake of matching
                name = company[0]
                name = re.sub(r"[.,]|\b(inc|corp|corporation|ltd|llc)\b", "", name)
                title = company[1]
                title = re.sub(r"[.,]|\b(inc|corp|corporation|ltd|llc)\b", "", title)

                for item in all_companies.values():
                    all_search = item["title"]
                    # sanitize company title and then compare to names/titles from fund filings
                    all_search = re.sub(r"[.,]| /NEW/", "", all_search)
                    if name.casefold() == all_search.casefold() or title.casefold() == all_search.casefold():
                        match_count += 1
                        company.append(item["ticker"])
                        # prepend zeroes to pad to length 10 for all 
                        company.append(str(item["cik_str"]).zfill(10))
                        break
            
            print(f"Successfully linked {match_count} company tickers and CIKs ({int(match_count/len(merged_companies)*100)}%) to representations in funds\n")

        else:
            print("Could not load SEC-registered company data\n")

        # [ name, title, lei, cusip, ticker, cik ]
        # pad with empty strings if we did not find the company ticker/CIK from the fund
        merged_companies = [row + [""] * (6 - len(row)) for row in merged_companies]
        
        # write the company data to a csv
        print(f"Writing company data to CSV")
        with open("scraped_companies.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(merged_companies)