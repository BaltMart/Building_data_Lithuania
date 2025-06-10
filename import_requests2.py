from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from bs4 import BeautifulSoup
import time
import pandas as pd
import re
import os

class ConstructionPermitScraper:
    def __init__(self, csv_file_path=None):
        self.base_url = "https://infostatyba.planuojustatau.lt/eInfostatyba-external/projectObject/projectObjectMain?uuid="
        self.csv_file_path = csv_file_path
        
    def load_uuids(self):
        if self.csv_file_path is None:
            print("No CSV file path provided")
            return []
            
        try:
            print(f"Reading CSV from: {self.csv_file_path}")
            if not os.path.exists(self.csv_file_path):
                print(f"Error: CSV file does not exist: {self.csv_file_path}")
                return []
                
            df = pd.read_csv(self.csv_file_path)
            print(f"CSV columns: {df.columns.tolist()}")
            
            if 'uuid' in df.columns:
                uuids = df['uuid'].tolist()
            else:
                print("Warning: No 'uuid' column found, using first column")
                uuids = df.iloc[:, 0].tolist()
            
            print(f"Found {len(uuids)} UUIDs")
            return uuids
        except Exception as e:
            print(f"Error loading CSV: {e}")
            return []

    def scrape_permit_data(self, uuid):
        url = self.base_url + uuid
        print(f"Starting to scrape URL: {url}")
        options = EdgeOptions()
        # options.add_argument('--headless')  # Uncomment for headless mode if needed
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        driver = None
        try:
            print("Initializing Edge driver...")
            service = EdgeService(EdgeChromiumDriverManager().install())
            driver = webdriver.Edge(service=service, options=options)
            print("Opening URL...")
            driver.get(url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".po-stage-header, .po-building-header"))
            )

            # Extract basic info
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            data = {
                'uuid': uuid,
                'address': None,
                'total_area': None,
                'new_buildings_count': None,
                'new_apartments_count': None,
                'stages': []
            }            # Extract address from the Statiniai section
            buildings_section = soup.find_all('span', class_='basic')
            for span in buildings_section:
                text = span.get_text(strip=True)
                # Look for address that appears after building type and construction type
                if '(' in text and ')' in text and ',' in text:
                    parts = text.split(',')
                    if len(parts) > 1:
                        # Take everything after the first comma as the address
                        data['address'] = ','.join(parts[1:]).strip()
                # Look for total area information
                if 'plotas' in text.lower() or 'kv. m' in text.lower():
                    area_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:m²|kv\.\s*m)', text)
                    if area_match:
                        data['total_area'] = float(area_match.group(1))

            # Extract area and counts from building panel
            building_panel = soup.find('span', class_='po-buildings-panel')
            if building_panel:
                counts = building_panel.find_all('span', class_='basic')
                for count in counts:
                    text = count.get_text(strip=True)
                    if 'pastatų skaičius' in text:
                        number = re.search(r'\d+', text)
                        if number:
                            data['new_buildings_count'] = int(number.group())
                    elif 'butų skaičius' in text:
                        number = re.search(r'\d+', text)
                        if number:
                            data['new_apartments_count'] = int(number.group())            # Extract stages and dates
            stages = driver.find_elements(By.CSS_SELECTOR, ".po-stage")
            for stage in stages:
                try:
                    # Find stage title
                    title_elem = stage.find_element(By.CSS_SELECTOR, ".po-stage-header__title")
                    stage_title = title_elem.text.strip()
                    
                    # Find dates in the stage's document list
                    date = ""
                    try:
                        # Get all document dates in this stage
                        doc_dates = stage.find_elements(By.CSS_SELECTOR, "td[data-label='Registracijos data']")
                        if doc_dates:
                            # Get the latest date
                            dates = []
                            for date_elem in doc_dates:
                                date_text = date_elem.text.strip()
                                if date_text and re.match(r'\d{4}-\d{2}-\d{2}', date_text):
                                    dates.append(date_text)
                            if dates:
                                # Sort dates in descending order and take the latest one
                                dates.sort(reverse=True)
                                date = dates[0]
                    except Exception as e:
                        print(f"Error extracting stage date: {e}")
                    
                    if stage_title:
                        data['stages'].append({'name': stage_title, 'date': date})
                except Exception as e:
                    print(f"Error extracting stage info: {e}")
                    continue

            return data
        except Exception as e:
            print(f"Error scraping {uuid}: {e}")
            return {'uuid': uuid, 'error': str(e)}
        finally:
            if driver:
                driver.quit()

    def scrape_permit_data_requests(self, uuid):
        import requests
        url = self.base_url + uuid
        print(f"Fetching URL with requests: {url}")
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            data = {
                'uuid': uuid,
                'address': None,
                'total_area': None,
                'new_buildings_count': None,
                'new_apartments_count': None,
                'stages': []
            }
            # Address: look for span.basic after po-building-header
            building_header = soup.find('span', class_='po-building-header')
            if building_header:
                address_elem = building_header.find_next('span', class_='basic')
                if address_elem:
                    data['address'] = address_elem.get_text(strip=True)
            # If not found, fallback to any span.basic that looks like an address
            if not data['address']:
                for span in soup.find_all('span', class_='basic'):
                    text = span.get_text(strip=True)
                    if re.search(r'\d+\s*[,\.]', text) and len(text) > 10:
                        data['address'] = text
                        break
            # Total area: look for 'plotas' or 'kv. m' in span.basic
            for span in soup.find_all('span', class_='basic'):
                text = span.get_text(strip=True)
                if 'plotas' in text.lower() or 'kv. m' in text.lower():
                    area_match = re.search(r'(\d+(?:[\.,]\d+)?)\s*(?:m²|kv\.\s*m)', text)
                    if area_match:
                        data['total_area'] = float(area_match.group(1).replace(',', '.'))
                        break
            # Building and apartment counts
            building_panel = soup.find('span', class_='po-buildings-panel')
            if building_panel:
                for span in building_panel.find_all('span', class_='basic'):
                    text = span.get_text(strip=True)
                    if 'pastatų skaičius' in text:
                        number = re.search(r'\d+', text)
                        if number:
                            data['new_buildings_count'] = int(number.group())
                    elif 'butų skaičius' in text:
                        number = re.search(r'\d+', text)
                        if number:
                            data['new_apartments_count'] = int(number.group())
            # Stages: find all po-stage-header__title
            for stage_title in soup.find_all('span', class_='po-stage-header__title'):
                name = stage_title.get_text(strip=True)
                data['stages'].append({'name': name, 'date': ''})
            return data
        except Exception as e:
            print(f"Error scraping {uuid} with requests: {e}")
            return {'uuid': uuid, 'error': str(e)}

    def scrape_all(self, output_file='construction_data.csv', delay=1):
        uuids = self.load_uuids()
        if not uuids:
            print("No UUIDs found in CSV file")
            return None
            
        print(f"Found {len(uuids)} UUIDs to scrape")
        results = []
        all_stage_names = set()
        
        for i, uuid in enumerate(uuids, 1):
            print(f"Scraping {i}/{len(uuids)}: {uuid}")
            data = self.scrape_permit_data(uuid)
            if 'stages' in data:
                for stage in data['stages']:
                    if stage['name']:
                        all_stage_names.add(stage['name'])
            results.append(data)
            if delay > 0:
                time.sleep(delay)
            if i % 10 == 0:
                print(f"Completed {i}/{len(uuids)} items")

        # Create DataFrame in wide format
        stage_columns = sorted(all_stage_names)
        records = []
        for data in results:
            row = {
                'uuid': data.get('uuid'),
                'address': data.get('address'),
                'total_area': data.get('total_area'),
                'new_buildings_count': data.get('new_buildings_count'),
                'new_apartments_count': data.get('new_apartments_count'),
            }
            # Add stage dates to columns
            stage_dates = {stage['name']: stage['date'] for stage in data.get('stages', []) if stage['name']}
            for stage_name in stage_columns:
                row[stage_name] = stage_dates.get(stage_name)
            records.append(row)

        df = pd.DataFrame(records)
        df.to_csv(output_file, index=False, encoding='utf-8')
        print(f"\nSummary:")
        print(f"Total records: {len(records)}")
        print(f"Records with addresses: {df['address'].notna().sum()}")
        print(f"\nColumns: {', '.join(df.columns)}")
        return df

# Example usage
if __name__ == "__main__":
    csv_path = r'C:\Users\mbaltramaitis\OneDrive - Lietuvos bankas\Documents\Building analysis project\uuids.csv'
    if not os.path.exists(csv_path):
        print(f"CSV file not found: {csv_path}")
    else:
        scraper = ConstructionPermitScraper(csv_path)
        results = scraper.scrape_all('construction_permits_data.csv', delay=2)
        if results:
            df = pd.DataFrame(results[:5])
            print("\nFirst 5 results:")
            print(df.to_string())