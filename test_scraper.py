from import_requests2 import ConstructionPermitScraper
import pandas as pd

if __name__ == "__main__":
    # Test with specific UUIDs without requiring a CSV file
    scraper = ConstructionPermitScraper()
    test_uuids = [
        'F8CCEDEBE4C94558864A4E692C5D60A3',
        '7BFF88EA979E4C09A876663013095BA3'
    ]
    print(f"\nTesting with UUIDs: {test_uuids}")
    output_path = r'C:\Users\mbaltramaitis\OneDrive - Lietuvos bankas\Documents\Building analysis project\test_output.csv'

    # Create results list and collect all stage names
    results = []
    all_stage_names = set()

    for i, uuid in enumerate(test_uuids, 1):
        print(f"\nScraping {i}/{len(test_uuids)}: {uuid}")
        data = scraper.scrape_permit_data(uuid)
        if 'stages' in data and data['stages']:
            for stage in data['stages']:
                if stage.get('name'):
                    all_stage_names.add(stage['name'])
        results.append(data)

    # Convert to wide format DataFrame
    if results:
        stage_columns = sorted(all_stage_names)
        records = []
        for data in results:
            row = {
                'uuid': data.get('uuid'),
                'address': data.get('address'),
                'total_area': data.get('total_area'),
                'new_buildings_count': data.get('new_buildings_count'),
                'new_apartments_count': data.get('new_apartments_count')
            }
            if 'stages' in data and data['stages']:
                stage_dates = {stage['name']: stage['date'] 
                             for stage in data['stages'] 
                             if stage.get('name')}
                for stage_name in stage_columns:
                    row[stage_name] = stage_dates.get(stage_name)
            else:
                for stage_name in stage_columns:
                    row[stage_name] = None
            records.append(row)
        df = pd.DataFrame(records)
        df.to_csv(output_path, index=False, encoding='utf-8')
        print("\nTest Results:")
        print(df.to_string())
        print(f"\nResults saved to: {output_path}")
        print("\nColumns in output:")
        for col in df.columns:
            non_null = df[col].notna().sum()
            print(f"- {col}: {non_null} non-null values")
    else:
        print("No results obtained")

# NOTE: If you get 'Could not reach host' or network errors, try commenting out the '--headless' line in import_requests2.py to debug with a visible browser.