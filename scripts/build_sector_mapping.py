"""
S&P 500 기업을 products_and_services.yaml의 하위 산업군에 매핑하는 고도화된 스크립트.
yfinance의 다양한 industry 명칭을 정규화하여 매핑률을 극대화하고,
사업 다각화 기업에 대한 다중 섹터 매핑을 적용한다.
"""

import yaml
import yfinance as yf
import time
import os
import json
import re

CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', 'config')

# yfinance industry → products_and_services 하위 산업군 매핑 규칙
# 대시(—, -) 등은 정규화 단계에서 처리되므로 표준 형식으로 정의
INDUSTRY_MAP = {
    # Energy
    'Oil & Gas E&P': 'oil and gas',
    'Oil & Gas Integrated': 'oil and gas',
    'Oil & Gas Midstream': 'oil and gas',
    'Oil & Gas Refining & Marketing': 'oil and gas',
    'Oil & Gas Equipment & Services': 'oil and gas',
    'Oil & Gas Drilling': 'oil and gas',
    'Solar': 'renewable energy',
    'Uranium': 'renewable energy',

    # Materials
    'Specialty Chemicals': 'chemicals',
    'Chemicals': 'chemicals',
    'Agricultural Inputs': 'chemicals',
    'Gold': 'metals and mining',
    'Copper': 'metals and mining',
    'Steel': 'metals and mining',
    'Other Industrial Metals & Mining': 'metals and mining',
    'Aluminum': 'metals and mining',
    'Building Materials': 'metals and mining',
    'Other Precious Metals & Mining': 'metals and mining',
    'Coking Coal': 'metals and mining',

    # Industrials
    'Aerospace & Defense': 'aerospace and defense',
    'Specialty Industrial Machinery': 'manufacturing',
    'Industrial Distribution': 'manufacturing',
    'Diversified Industrials': 'manufacturing',
    'Electrical Equipment & Parts': 'manufacturing',
    'Farm & Heavy Construction Machinery': 'manufacturing',
    'Metal Fabrication': 'manufacturing',
    'Tools & Accessories': 'manufacturing',
    'Pollution & Treatment Controls': 'manufacturing',
    'Industrial Conglomerates': 'manufacturing',
    'Railroads': 'transportation and logistics',
    'Airlines': 'transportation and logistics',
    'Trucking': 'transportation and logistics',
    'Integrated Freight & Logistics': 'transportation and logistics',
    'Marine Shipping': 'transportation and logistics',
    'Air Freight & Logistics': 'transportation and logistics',
    'Airports & Air Services': 'transportation and logistics',
    'Waste Management': 'manufacturing',
    'Rental & Leasing Services': 'manufacturing',
    'Consulting Services': 'manufacturing',
    'Specialty Business Services': 'manufacturing',
    'Security & Protection Services': 'manufacturing',
    'Conglomerates': 'manufacturing',
    'Staffing & Employment Services': 'manufacturing',
    'Engineering & Construction': 'manufacturing',
    'Building Products & Equipment': 'manufacturing',

    # Consumer Discretionary
    'Auto Manufacturers': 'automobiles',
    'Auto Parts': 'automobiles',
    'Auto & Truck Dealerships': 'automobiles',
    'Internet Retail': 'retail and e-commerce',
    'Specialty Retail': 'retail and e-commerce',
    'Home Improvement Retail': 'retail and e-commerce',
    'Apparel Retail': 'retail and e-commerce',
    'Department Stores': 'retail and e-commerce',
    'Discount Stores': 'retail and e-commerce',
    'Luxury Goods': 'retail and e-commerce',
    'Apparel Manufacturing': 'retail and e-commerce',
    'Footwear & Accessories': 'retail and e-commerce',
    'Furnishings, Fixtures & Appliances': 'retail and e-commerce',
    'Residential Construction': 'retail and e-commerce',
    'Leisure': 'hotels and leisure',
    'Resorts & Casinos': 'hotels and leisure',
    'Lodging': 'hotels and leisure',
    'Restaurants': 'hotels and leisure',
    'Travel Services': 'hotels and leisure',
    'Gambling': 'hotels and leisure',
    'Cruise Lines': 'hotels and leisure',

    # Consumer Staples
    'Beverages - Non-Alcoholic': 'food and beverage',
    'Beverages - Brewers': 'food and beverage',
    'Beverages - Wineries & Distilleries': 'food and beverage',
    'Packaged Foods': 'food and beverage',
    'Confectioners': 'food and beverage',
    'Food Distribution': 'food and beverage',
    'Grocery Stores': 'food and beverage',
    'Farm Products': 'agriculture',
    'Tobacco': 'food and beverage',
    'Household & Personal Products': 'household and personal products',
    'Personal Care Products': 'household and personal products',
    'Education & Training Services': 'household and personal products',
    'Packaging & Containers': 'household and personal products',

    # Health Care
    'Drug Manufacturers - General': 'pharmaceuticals and biotech',
    'Drug Manufacturers - Specialty & Generic': 'pharmaceuticals and biotech',
    'Biotechnology': 'pharmaceuticals and biotech',
    'Diagnostics & Research': 'pharmaceuticals and biotech',
    'Medical Instruments & Supplies': 'medical devices',
    'Medical Devices': 'medical devices',
    'Health Information Services': 'health services',
    'Medical Care Facilities': 'health services',
    'Healthcare Plans': 'health services',
    'Medical Distribution': 'health services',
    'Pharmaceutical Retailers': 'health services',

    # Financials
    'Banks - Diversified': 'banking',
    'Banks - Regional': 'banking',
    'Credit Services': 'banking',
    'Mortgage Finance': 'banking',
    'Insurance - Life': 'insurance',
    'Insurance - Diversified': 'insurance',
    'Insurance - Property & Casualty': 'insurance',
    'Insurance - Specialty': 'insurance',
    'Insurance - Reinsurance': 'insurance',
    'Insurance Brokers': 'insurance',
    'Asset Management': 'asset management',
    'Capital Markets': 'asset management',
    'Financial Data & Stock Exchanges': 'asset management',
    'Financial Conglomerates': 'asset management',
    'Private Equity': 'asset management',

    # Information Technology
    'Software - Application': 'software',
    'Software - Infrastructure': 'software',
    'Information Technology Services': 'software',
    'Semiconductors': 'semiconductors',
    'Semiconductor Equipment & Materials': 'semiconductors',
    'Consumer Electronics': 'hardware and IT equipment',
    'Computer Hardware': 'hardware and IT equipment',
    'Electronic Components': 'hardware and IT equipment',
    'Scientific & Technical Instruments': 'hardware and IT equipment',
    'Communication Equipment': 'hardware and IT equipment',
    'Data Storage': 'hardware and IT equipment',
    'Electronics & Computer Distribution': 'hardware and IT equipment',

    # Communication Services
    'Telecom Services': 'telecom',
    'Internet Content & Information': 'internet platforms',
    'Electronic Gaming & Multimedia': 'media and entertainment',
    'Entertainment': 'media and entertainment',
    'Broadcasting': 'media and entertainment',
    'Publishing': 'media and entertainment',
    'Advertising Agencies': 'media and entertainment',
    'Pay TV': 'media and entertainment',

    # Utilities
    'Utilities - Regulated Electric': 'electric utilities',
    'Utilities - Regulated Gas': 'gas and water utilities',
    'Utilities - Regulated Water': 'gas and water utilities',
    'Utilities - Independent Power Producers': 'electric utilities',
    'Utilities - Renewable': 'electric utilities',
    'Utilities - Diversified': 'electric utilities',

    # Real Estate
    'REIT - Diversified': 'REITs',
    'REIT - Industrial': 'REITs',
    'REIT - Office': 'REITs',
    'REIT - Residential': 'REITs',
    'REIT - Retail': 'REITs',
    'REIT - Specialty': 'REITs',
    'REIT - Hotel & Motel': 'REITs',
    'REIT - Healthcare Facilities': 'REITs',
    'REIT - Mortgage': 'REITs',
    'Real Estate Services': 'real estate services',
    'Real Estate - Development': 'real estate services',
    'Real Estate - Diversified': 'real estate services',
    'Real Estate Development': 'real estate services',
    'Real Estate Diversified': 'real estate services',
}

# 서비스/기타 특수 매핑
SPECIAL_MAP = {
    'Personal Services': 'household and personal products',
    'Home Improvement Retail': 'retail and e-commerce',
    'Department Stores': 'retail and e-commerce',
}

# 사업 다각화 기업의 보조 산업군 매핑
MULTI_SECTOR_MAP = {
    'AAPL': ['semiconductors', 'media and entertainment', 'software', 'banking'],
    'AMZN': ['retail and e-commerce', 'software', 'media and entertainment'],
    'GOOGL': ['software', 'media and entertainment', 'semiconductors'],
    'GOOG': ['software', 'media and entertainment', 'semiconductors'],
    'META': ['software', 'media and entertainment'],
    'MSFT': ['software', 'semiconductors', 'media and entertainment'],
    'TSLA': ['renewable energy', 'software'],
    'XOM': ['chemicals'],
    'CVX': ['chemicals'],
    'PSX': ['chemicals'],
    'DOW': ['manufacturing'],
    'BA': ['transportation and logistics', 'manufacturing'],
    'RTX': ['manufacturing'],
    'LMT': ['software'],
    'GE': ['renewable energy'],
    'HON': ['software', 'aerospace and defense'],
    'JNJ': ['medical devices', 'household and personal products'],
    'ABT': ['pharmaceuticals and biotech'],
    'TMO': ['manufacturing'],
    'DHR': ['pharmaceuticals and biotech'],
    'T': ['media and entertainment'],
    'TMUS': ['internet platforms'],
    'DIS': ['internet platforms', 'hotels and leisure'],
    'CMCSA': ['internet platforms', 'telecom'],
    'NFLX': ['software'],
    'WMT': ['software'],
    'COST': ['food and beverage'],
    'HD': ['manufacturing'],
    'JPM': ['software'],
    'GS': ['software'],
    'BLK': ['software'],
    'IBM': ['hardware and IT equipment'],
    'ORCL': ['hardware and IT equipment'],
    'ACN': ['software'],
    'NVDA': ['software'],
    'INTC': ['manufacturing'],
    'AVGO': ['software'],
    'KO': ['retail and e-commerce'],
    'PEP': ['retail and e-commerce', 'agriculture'],
    'MCD': ['real estate services'],
    'CAT': ['metals and mining'],
    'DE': ['agriculture', 'software'],
    'UBER': ['software', 'food and beverage'],
}


def normalize_string(s):
    """문자열 정규화 (대시 기호 통합 등)"""
    if not s: return ""
    # 유니코드 에 대시(—) 등을 일반 대시(-)로 변경하고 공백 정문화
    s = s.replace('—', ' - ').replace('–', ' - ')
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def load_tickers():
    with open(os.path.join(CONFIG_DIR, 'snp500.yaml'), 'r') as f:
        data = yaml.safe_load(f)
    return data.get('default_ticker_companies', {})


def fetch_sector_info(tickers, batch_size=50):
    results = {}
    ticker_list = list(tickers.keys())
    total = len(ticker_list)

    for i in range(0, total, batch_size):
        batch = ticker_list[i:i+batch_size]
        print(f"  [{i+1}-{min(i+batch_size, total)}/{total}] Fetching...")
        batch_str = ' '.join(batch)
        batch_tickers = yf.Tickers(batch_str)

        for ticker in batch:
            try:
                info = batch_tickers.tickers[ticker].info
                sector = info.get('sector', 'Unknown')
                industry = info.get('industry', 'Unknown')
                results[ticker] = {
                    'name': tickers[ticker],
                    'sector': sector,
                    'industry': industry,
                }
            except:
                results[ticker] = {'name': tickers.get(ticker, ticker), 'sector': 'Unknown', 'industry': 'Unknown'}
        time.sleep(1)
    return results


def map_to_subcategory(ticker, info):
    categories = set()
    industry = normalize_string(info.get('industry', 'Unknown'))
    
    # 1차: 완벽 일치 확인 (정규화 후)
    found = False
    for key, val in INDUSTRY_MAP.items():
        if normalize_string(key) == industry:
            categories.add(val)
            found = True
            break
            
    # 2차: 부분 일치 확인 (주요 키워드)
    if not found:
        if 'REIT' in industry: categories.add('REITs')
        elif 'Software' in industry: categories.add('software')
        elif 'Utility' in industry:
            if 'Gas' in industry or 'Water' in industry: categories.add('gas and water utilities')
            else: categories.add('electric utilities')
        elif 'Insurance' in industry: categories.add('insurance')
        elif 'Bank' in industry: categories.add('banking')
        elif industry in SPECIAL_MAP: categories.add(SPECIAL_MAP[industry])

    # 3차: 다중 산업군 규칙
    if ticker in MULTI_SECTOR_MAP:
        for cat in MULTI_SECTOR_MAP[ticker]:
            categories.add(cat)

    return list(categories)


def build_mapping(sector_info):
    category_companies = {}
    unmapped = []
    for ticker, info in sector_info.items():
        cats = map_to_subcategory(ticker, info)
        if not cats:
            unmapped.append((ticker, info['name'], info.get('industry', '?')))
            continue
        for cat in cats:
            category_companies.setdefault(cat, []).append(ticker)
    return category_companies, unmapped


def write_products_yaml(category_companies):
    sector_order = [
        ('Energy', ['oil and gas', 'renewable energy']),
        ('Materials', ['chemicals', 'metals and mining']),
        ('Industrials', ['aerospace and defense', 'manufacturing', 'transportation and logistics']),
        ('Consumer Discretionary', ['automobiles', 'retail and e-commerce', 'hotels and leisure']),
        ('Consumer Staples', ['food and beverage', 'household and personal products', 'agriculture']),
        ('Health Care', ['pharmaceuticals and biotech', 'medical devices', 'health services']),
        ('Financials', ['banking', 'insurance', 'asset management']),
        ('Information Technology', ['software', 'semiconductors', 'hardware and IT equipment']),
        ('Communication Services', ['telecom', 'media and entertainment', 'internet platforms']),
        ('Utilities', ['electric utilities', 'gas and water utilities']),
        ('Real Estate', ['REITs', 'real estate services']),
    ]
    lines = []
    for sector_name, subcats in sector_order:
        lines.append(f'# {sector_name}')
        for subcat in subcats:
            tickers = sorted(category_companies.get(subcat, []))
            lines.append(f'{subcat}:')
            for t in tickers: lines.append(f'  - {t}')
        lines.append('')
    with open(os.path.join(CONFIG_DIR, 'products_and_services.yaml'), 'w') as f:
        f.write('\n'.join(lines))


def main():
    print("=== S&P 500 → 산업군 매핑 시작 (고도화 버전) ===\n")
    tickers = load_tickers()
    sector_info = fetch_sector_info(tickers)
    category_companies, unmapped = build_mapping(sector_info)
    
    print(f"\n매핑 완료: {len(tickers)-len(unmapped)}/{len(tickers)}개 기업 성공")
    if unmapped:
        print(f"미매핑 기업 ({len(unmapped)}개):")
        for t, n, i in unmapped[:20]: print(f"  {t}: {n} ({i})")
        
    write_products_yaml(category_companies)
    print("\n✅ products_and_services.yaml 업데이트 완료")


if __name__ == '__main__':
    main()
