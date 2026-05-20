"""
Check extracted data for duplicates and quality
"""
import json
import os
from collections import Counter
from config.settings import DATA_DIR, PLACE_CATEGORIES


def check_json_file(filename: str):
    """
    Check a JSON file for duplicates and data quality
    """
    filepath = os.path.join(DATA_DIR, filename)
    
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filename}")
        return
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"\n{'='*60}")
    print(f"📄 {filename}")
    print(f"{'='*60}")
    
    # Check duplicates by place_id
    place_ids = [item.get('place_id') for item in data]
    duplicates = [pid for pid, count in Counter(place_ids).items() if count > 1]
    
    if duplicates:
        print(f"⚠️  DUPLICATES FOUND: {len(duplicates)}")
        for dup_id in duplicates[:5]:  # Show first 5
            dup_items = [item for item in data if item.get('place_id') == dup_id]
            print(f"   • {dup_items[0].get('name')} appears {len(dup_items)} times")
    else:
        print(f"✅ NO DUPLICATES - All {len(data)} places are unique")
    
    # Check data completeness
    fields = ['name', 'address', 'coordinates', 'place_id']
    missing = {field: 0 for field in fields}
    
    for item in data:
        for field in fields:
            if not item.get(field):
                missing[field] += 1
    
    print(f"\n📊 Data Completeness:")
    print(f"   Total places: {len(data)}")
    
    for field, count in missing.items():
        percentage = (len(data) - count) / len(data) * 100 if data else 0
        status = "✅" if percentage > 95 else "⚠️"
        print(f"   {status} {field:15}: {percentage:.1f}% complete")
    
    # Optional fields
    optional = ['phone_number', 'website', 'opening_hours', 'rating']
    print(f"\n📌 Optional Data:")
    for field in optional:
        count = sum(1 for item in data if item.get(field))
        percentage = count / len(data) * 100 if data else 0
        print(f"   • {field:15}: {percentage:.1f}% ({count}/{len(data)})")
    
    # Governorate distribution
    if data and 'governorate' in data[0]:
        govs = Counter([item.get('governorate', 'Unknown') for item in data])
        print(f"\n🗺️  Distribution by Governorate:")
        for gov, count in govs.most_common(10):
            print(f"   • {gov:20}: {count:3} places")
        
        if len(govs) > 10:
            print(f"   ... and {len(govs) - 10} more")


def check_all_data():
    """
    Check all JSON files
    """
    print("=" * 60)
    print("DATA QUALITY CHECK - TUNISIA MEDICAL DATA")
    print("=" * 60)
    
    total_places = 0
    
    for category_key, category_config in PLACE_CATEGORIES.items():
        filename = category_config['filename']
        check_json_file(filename)
        
        filepath = os.path.join(DATA_DIR, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                total_places += len(data)
    
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total medical establishments: {total_places}")
    print(f"Total categories: {len(PLACE_CATEGORIES)}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    check_all_data()