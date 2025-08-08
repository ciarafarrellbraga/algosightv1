from bs4 import BeautifulSoup
import requests
import re
import spacy
import pycountry
from collections import defaultdict, Counter
def name_to_cik(company_name):
    headers = {
    "User-Agent": "Algosight (contact: ciarafarrellbraga@gmail.com)"
    }
    search_url = f"https://www.sec.gov/files/company_tickers.json"
    r = requests.get(search_url, headers=headers)
    data = r.json()
    for entry in data.values():
        if company_name.lower() in entry['title'].lower():
            return str(entry['cik_str']).zfill(10)  # pad with zeroes

    raise Exception("CIK not found.")

def latest_10k(company_name):
    cik=name_to_cik(company_name)
    headers = {
    "User-Agent": "Algosight (contact: ciarafarrellbraga@gmail.com)"
    }
    search_url =f"https://data.sec.gov/submissions/CIK{cik}.json"
    r = requests.get(search_url, headers=headers)
    data = r.json()
    filings = data["filings"]["recent"]
    for i, form_type in enumerate(filings["form"]):
        if form_type == "10-K":
            accession_number = filings["accessionNumber"][i].replace("-", "")
            primary_doc = filings["primaryDocument"][i]
            filing_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_number}/{primary_doc}"
            filing_resp=requests.get(filing_url,headers=headers)
            return filing_resp.text
    raise Exception("10-K filing not found.") 
def clean_text (company_name):
    html=latest_10k(company_name)
    soup=BeautifulSoup(html,'html.parser')
    text=soup.get_text(separator='', strip=True)
    return text

def extract_sections(company_name):
    text = clean_text(company_name)
    section_patterns = [
        ('Item 1. Business', r'Item\s+1\.*\s*Business'),
        ('Item 1A. Risk Factors', r'Item\s+1A\.*\s*Risk\s*Factors'),
        ('Item 2. Properties', r'Item\s+2\.*\s*Properties'),
        ('Item 7. MD&A', r'Item\s+7\.*\s*Management.*?Discussion.*?'),
    ]
    matches = []
    for name, pattern in section_patterns:
        all_matches=list(re.finditer(pattern, text, re.I))
        if all_matches:
            match=all_matches[-1]
            matches.append((name, match.start()))
        if not matches :
            return {}
        
        matches.sort(key=lambda x:x[1])
        sections_text = {}
   
        for i in range(len(matches)):
            name, start = matches[i]
            end = matches[i + 1][1] if i + 1 < len(matches) else len(text)
            section_text = text[start:end].strip()
            sections_text[name] = section_text

    return sections_text

nlp = spacy.load("en_core_web_sm")
all_subdivisions = set(sub.name for sub in pycountry.subdivisions)
def loc_to_country (gpe):
    try:
        subs = [sub for sub in pycountry.subdivisions if sub.name.lower() == gpe.lower()]
        if subs:
            country_code=subs[0].country_code
            country=pycountry.countries.get(alpha_2=country_code)
            if country:
                return country.name
        match=pycountry.countries.search_fuzzy(gpe.strip())
        return match[0].name
    except LookupError:
        return None

def country_extractor(company_name):
    section=extract_sections(company_name)
    country_section_library=defaultdict(lambda: defaultdict(int))
    for section_name, section_text in section.items():
        doc=nlp(section_text)
        gpes= [ent.text.strip() for ent in doc.ents if ent.label_=="GPE"]
        for gpe in gpes:
            country=loc_to_country(gpe)
            if country:
                country_section_library[country][section_name] +=1
    
    return {country:dict(sections) for country, sections in country_section_library.items()}
print(country_extractor("Uber")) 
