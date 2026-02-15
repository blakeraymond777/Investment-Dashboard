import requests
import re

def determine_exposure(company_name_to_check, portfolio):
    company_exposure = 0         # Dollars USD
    for position in portfolio:
        ticker = position[0]
        url = funds.get(ticker)
        if url is not None:
            company_exposure += float(get_holdings_percentage_from_nport(company_name_to_check, url) * position[1])
        else:
            print(f"No fund found with that ticker. Skipping {position[1]} share/s of \"{ticker}\" position in results")

    return company_exposure

def get_holdings_percentage_from_nport(company_name, url):
    """
    Extract holdings from SEC NPORT filing
    
    Args:
        url: Direct URL to the NPORT XML/TXT file
    """
    # Fetch the file
    headers = {"User-Agent": "PersonalInvestmentApp blakeraymond777@gmail.com"}
    response = requests.get(url, headers=headers)
    text = response.text
    
    # Extract all holdings with names and percentages using regex
    # Pattern looks for <name> or <title> followed by <pctVal>
    
    # Find all investment securities sections
    investments = re.findall(r'<invstOrSec>.*?</invstOrSec>', text, re.DOTALL)

    for inv in investments:
        # Get name (try <name> first, then <title>)
        name_match = re.search(re.escape(company_name), inv, re.IGNORECASE)
        # search by title if needed
        # if not name_match:
        #     name_match = re.search(r'<title>(.*?)</title>', inv)
        
        # Get percentage
        if name_match:
            pct_match = re.search(r'<pctVal>(.*?)</pctVal>', inv)
            if pct_match:
                return float(pct_match.group(1))
    
    return 0

#### Main logic code to run ####

# Declare variables
# MVP: hardcode portfolio to check ([["ticker1", num shares held], ["ticker2", num shares held]])
portfolio = [["VFIAX", 1000], ["FXAIX", 1000]]

# Hardcode common funds txt links
# TODO: need to find a way to dynamically get the most recent NPORT txt file from the company page (rather than the hardcoded NPORT page path)
# TODO: differentiate between different kinds of shares of the same underlying fund (ETF vs Admiral Shares)
# change structure to "Ticker": ["N-PORT link", "type of shares", "name of fund"]? 
# more fidelity funds: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000819118&owner=include&count=40
funds = {
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

# Determine fund tickers/names to be checked (representing the whole portfolio) 
# Create list of txt files from EDGAR containing holdings
# If hardcoded, use local, else search EDGAR to find txt file
# for position in portfolio:
#     ticker = position[0]
#     if ticker in common_funds:
#         position.append(common_funds[ticker])
#     else:
#         # TODO: put user breakpoint here to skip the fund if unknown
#         # lookup_fund(ticker)
#         print(f"No fund with that ticker found. Skipping ${ticker} in results")

print(portfolio)

# Determine function to be run
# MVP: lookup single stock exposure (get through prompting or hardcoding)
# must be in legal name format: AMZN = Amazon.com Inc
# convert tickers into legal names (use LEI)
COMPANIES_TO_SEARCH = ["Amazon.com Inc", "Netflix"]

# TODO: avoid doubling back and search for each on every portfolio position rather than by security
for company in COMPANIES_TO_SEARCH:
    company_exposure = determine_exposure(company, portfolio)
    print(f"Exposure to {company}: ${round(company_exposure, 2)}")

# Lookup stock into each fund on (txt) list and use weight to determine proportional holding
# Determine user value of certain holding (NAV * num shares held) and holding of lookup stock (weight % of lookup * num shares held)


# Sum each individual position per fund across all funds
# MVP: do this process linearly (stretch is to add parallelism)

