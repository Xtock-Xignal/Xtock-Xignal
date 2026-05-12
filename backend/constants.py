
# 1. NLTK 의존성 제거 -> 하드코딩된 불용어 리스트 사용
NLTK_STOPWORDS = {
    'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', "you're", "you've", "you'll", "you'd", 'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', "she's", 'her', 'hers', 'herself', 'it', "it's", 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which', 'who', 'whom', 'this', 'that', "that'll", 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with', 'about', 'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 'will', 'just', 'don', "don't", 'should', "should've", 'now', 'd', 'll', 'm', 'o', 're', 've', 'y', 'ain', 'aren', "aren't", 'couldn', "couldn't", 'didn', "didn't", 'doesn', "doesn't", 'hadn', "hadn't", 'hasn', "hasn't", 'haven', "haven't", 'isn', "isn't", 'ma', 'mightn', "mightn't", 'mustn', "mustn't", 'needn', "needn't", 'shan', "shan't", 'shouldn', "shouldn't", 'wasn', "wasn't", 'weren', "weren't", 'won', "won't", 'wouldn', "wouldn't"
}

# 기본 불용어 집합 설정
STOPWORDS = set(NLTK_STOPWORDS)

# 불용어에서 제외할 티커 목록
TICKER_STOPWORDS_EXCEPTION = {'it', 'on', 'be', 'do', 'no', 'up', 'all', 'a', 'can', 'or', 'so', 'key'}
STOPWORDS = STOPWORDS - TICKER_STOPWORDS_EXCEPTION

# 커스텀 비즈니스 불용어
BUSINESS_STOPWORDS ={
    'inc', 'corp', 'company', 'ltd', 'incorporated', 'group', 'class', 'plc', 'holding', 'holdings',
    'firm', 'shares', 'stock', 'business', 'corporate', 'operations', 'segment', 'global', 'international',
    'services', 'solutions', 'systems', 'products', 'industries', 'technologies'
}
STOPWORDS.update(BUSINESS_STOPWORDS)

# 2. 기업 별칭 (검색 정확도 핵심)
ALIASES = {
    # Big Tech
    "AAPL": ["apple", "iphone", "ipad", "macbook", "ios", "vision pro", "tim cook"],
    "GOOGL": ["google", "android", "youtube", "gmail", "pixel", "deepmind", "gemini", "sundar pichai"],
    "GOOG":  ["google", "android", "youtube", "gmail", "pixel", "deepmind", "gemini"],
    "MSFT":  ["microsoft", "xbox", "windows", "office 365", "copilot", "azure", "satya nadella"],
    "AMZN":  ["amazon", "aws", "prime day", "alexa", "jeff bezos", "andy jassy"],
    "META":  ["facebook", "instagram", "whatsapp", "oculus", "zuck", "mark zuckerberg"],
    "TSLA":  ["tesla", "cybertruck", "optimus", "model 3", "model y", "elon musk", "spacex"],
    "NVDA":  ["nvidia", "geforce", "rtx", "h100", "blackwell", "jensen huang", "cuda"],
    
    # Ambiguous Tickers 보완
    "ALL": ["allstate", "allstate insurance"],
    "O":   ["realty income", "monthly dividend company"],
    "IT":  ["gartner"],
    "SO":  ["southern company"],
    "A":   ["agilent", "agilent technologies"],
    
    # Finance / Others
    "JPM": ["jpmorgan", "jamie dimon", "chase bank"],
    "BRK.B": ["berkshire hathaway", "warren buffett", "charlie munger"],
    "LLY": ["eli lilly", "mounjaro", "zepbound"],
    "NVO": ["novo nordisk", "ozempic", "wegovy"],
    "AMD": ["lisa su", "ryzen", "epyc", "radeon"],
    "INTC": ["intel", "pat gelsinger"],
    "NFLX": ["netflix", "squid game"],
    "DIS": ["disney", "pixar", "marvel", "bob iger", "espn"],
    "COIN": ["coinbase", "brian armstrong"],
    "BA": ["boeing", "737 max"],
}

# 3. Ambiguous Tickers
AMBIGUOUS_TICKERS = {
    "ALL", "O", "A", "IT", "ON", "SO", "NOW", "ARE", "CAN", "WELL", "OR", "BE", "KEY", "PH"
}

# 4. Wikipedia 검색용 수동 매핑
MANUAL_MAPPING = {
    "O": "Realty Income",
    "T": "AT&T",
    "C": "Citigroup",
    "F": "Ford Motor Company",
    "V": "Visa Inc.",
    "M": "Macy's",
    "A": "Agilent Technologies",
    "D": "Dominion Energy",
    "E": "Eni",
    "K": "Kellogg Company",
    "ALL": "Allstate",
    "KEY": "KeyCorp",
    "PH":  "Parker Hannifin",
    "SO":  "Southern Company",
    "ED":  "Consolidated Edison",
    "BA":  "Boeing",
    "CAT": "Caterpillar Inc.",
    "DD":  "DuPont",
    "DG":  "Dollar General",
    "MA":  "Mastercard",
    "MO":  "Altria",
    "MU":  "Micron Technology",
    "PM":  "Philip Morris International",
    "RF":  "Regions Financial Corporation",
    "ST":  "Sensata Technologies",
    "TJX": "TJX Companies",
    "UPS": "United Parcel Service",
    "WM":  "Waste Management (corporation)",
    "GOOG": "Alphabet Inc.",
    "GOOGL": "Alphabet Inc.",
    "AMZN": "Amazon (company)",
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft",
    "META": "Meta Platforms",
    "TSLA": "Tesla, Inc.",
    "NVDA": "Nvidia",
    "PODD": "Insulet", 
    "BF-B": "Brown-Forman", 
    "BRK-B": "Berkshire Hathaway", 
    "SOLV": "Solventum", 
    "KVUE": "Kenvue",
    "GEHC": "GE HealthCare"
}

# 5. 일반적인 회사 키워드
GENERIC_KEYWORDS = {
    "tech", "technology", "technologies", "software", "hardware", "system", "systems", 
    "group", "global", "international", "service", "services", "solution", "solutions", 
    "company", "companies", "corp", "corporation", "holding", "holdings", 
    "inc", "ltd", "plc", "investment", "capital", "financial", "finance", "business",
    "sector", "industry", "provider", "offers", "provides", "operates", "headquartered",
    "subsidiaries", "subsidiary", "listed", "public", "private", "conglomerate",
    "component", "components", "index", "indices", "stock", "market", "nasdaq", "nyse",
    "role", "filled", "became", "become", "based", "located", "place",
    "history", "founded", "founder", "established", "incorporated",
    "lawsuit", "sued", "legal", "settlement", "alleged", "accused", "violation", "investigation",
    "controversy", "controversies", "ethical", "criticized", "criticism", "faced", "facing",
    "bankruptcy", "bankrupt", "debt", "stolen", "seized", "account",
    "termination", "terminated", "layoff", "layoffs", "mass", "fired", "resignation",
    "antitrust", "monopoly", "fine", "fined", "penalty", "judge", "court",
    "uber", "russia", "china", "eu", "european", "commission",
    "largest", "biggest", "world", "major", "widely", "described", "numerous", "various",
    "united", "states", "american", "california", "york", "mountain", "view", 
    "million", "billion", "trillion", "revenue", "profit", "income", "year", "years",
    "ceo", "announced", "appointed", "member", "board", "executive", "officer",
    "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december",
    "law", "actions", "action", "discovered", "access", "self", "greater", 
    "multiple", "large", "cap", "products", "services", "solutions", "platforms",
    "customer", "customers", "operations", "operate", "operating", "segment",
    "also", "include", "includes", "including", "related", "various", "involved",
    "based", "tools", "internet", "digital", "content", "devices", "apps"
}