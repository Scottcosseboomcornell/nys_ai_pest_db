#!/usr/bin/env python3
"""
Pesticide Category Lookup Table
Maps original EPA categories to simplified categories for the dropdown
"""

# Lookup table mapping original categories to simplified categories
PEST_CATEGORY_LOOKUP = {
    # Fungicide variations
    'Fungicide': 'Fungicide',
    'Fungicide/Fungistat': 'Fungicide',
    'Fungistat': 'Fungicide',
    'Fungicide And Nematicide': 'Fungicide',  # Split into separate categories
    
    # Herbicide variations
    'Herbicide': 'Herbicide',
    'Herbicide Terrestrial': 'Herbicide',
    'Herbicide Aquatic': 'Herbicide',
    
    # Insecticide variations
    'Insecticide': 'Insecticide',
    'Insecticide Synergist': 'Insecticide',
    'Insect Growth Regulator': 'Insecticide',
    'Termiticide': 'Insecticide',  # Termiticide under Insecticide
    
    # Bacteriocide variations
    'Bacteriocide': 'Bacteriocide',
    'Bacteriocide/Bacteriostat': 'Bacteriocide',
    'Bacteriostat': 'Bacteriocide',
    'Antibiotic': 'Bacteriocide',  # Antibiotic under Bacteriocide
    
    # Microbicide variations
    'Microbicide': 'Microbicide',
    'Microbicide/Microbistat': 'Microbicide',
    'Microbistat': 'Microbicide',
    'Microbial Pesticide': 'Microbicide',  # Microbial Pesticide under Microbicide
    'Nonviable Microbial/Transgenic Plant': 'Microbicide',  # Also under Microbicide
    
    # Disinfectant/Sanitizer variations
    'Disinfectant': 'Disinfectant',
    'Sanitizer': 'Disinfectant',
    'Sterilizer': 'Disinfectant',
    'Antimicrobial': 'Disinfectant',
    
    # Algaecide variations
    'Algaecide': 'Algaecide',
    'Algicide': 'Algaecide',
    'Slimacide': 'Algaecide',
    'Slimacides': 'Algaecide',
    
    # Rodenticide variations
    'Rodenticide': 'Rodenticide',
    'Poison': 'Rodenticide',
    
    # Repellent variations
    'Repellent': 'Repellent',
    'Repellent Or Feeding Depressant': 'Repellent',
    'Feeding Depressant': 'Repellent',
    
    # Attractant variations
    'Attractant': 'Attractant',
    'Sex Attractant': 'Attractant',
    'Sex Attractant Or Feeding Stimulant': 'Attractant',
    'Mating Disruptant': 'Attractant',
    
    # Fumigant variations
    'Fumigant': 'Fumigant',
    'Soil Fumigant': 'Fumigant',
    
    # Plant Growth variations
    'Plant Growth Regulator': 'Plant Growth Regulator',
    'Plant Growth Stimulator': 'Plant Growth Regulator',
    'Regulator': 'Plant Growth Regulator',
    
    # Virucide variations
    'Virucide': 'Virucide',
    'Tuberculocide': 'Virucide',
    'Sporicide': 'Virucide',
    
    # Specialized categories (keep as-is)
    'Miticide': 'Miticide',
    'Acaricide': 'Miticide',  # Acaricide under Miticide
    'Nematicide': 'Nematicide',
    'Molluscicide': 'Molluscicide',
    'Molluscicide And Tadpole Shrimp': 'Molluscicide',
    'Tadpole Shrimpicide': 'Molluscicide',
    'Avicide': 'Avicide',
    'Defoliant': 'Defoliant',
    'Desiccant': 'Desiccant',
    'Fertilizer': 'Fertilizer',
    'Biochemical Pesticide': 'Biochemical Pesticide',
    'Biocide': 'Biocide',
    'Antifoulant': 'Antifoulant',
    'Antifouling': 'Antifoulant',  # Antifouling under Antifoulant
    'Contraceptive': 'Contraceptive',
    'Chemosterilant': 'Chemosterilant',
    'Mechanical': 'Mechanical',
    'Industrial Chemical': 'Industrial Chemical',
    'Fire Retardant': 'Fire Retardant',
    'Medical Waste Treatment': 'Medical Waste Treatment',
    'Single Dose': 'Single Dose',
    'Multiple Dose': 'Multiple Dose',
    
    # Water treatment variations
    'Water Purifier Bacteriacidal': 'Water Treatment',
    'Water Purifier Bacteriastatic': 'Water Treatment',
    'Water Purifier Bacteriostat': 'Water Treatment',
}

def get_simplified_category(original_category):
    """
    Get the simplified category for a given original category.
    
    Args:
        original_category (str): The original EPA category
        
    Returns:
        str: The simplified category, or the original if no mapping exists
    """
    if not original_category or original_category in ['?', 'N/A']:
        return original_category
    
    return PEST_CATEGORY_LOOKUP.get(original_category, original_category)

def get_all_simplified_categories():
    """
    Get all unique simplified categories.
    
    Returns:
        list: Sorted list of all simplified categories
    """
    simplified_categories = set(PEST_CATEGORY_LOOKUP.values())
    return sorted(list(simplified_categories))

def get_categories_for_pesticide(pest_cat_string):
    """
    Get simplified categories for a pesticide with comma-separated categories.
    
    Args:
        pest_cat_string (str): Comma-separated string of original categories
        
    Returns:
        list: List of simplified categories
    """
    if not pest_cat_string or pest_cat_string in ['?', 'N/A']:
        return []
    
    original_categories = [cat.strip() for cat in pest_cat_string.split(',') if cat.strip()]
    simplified_categories = []
    
    for original_cat in original_categories:
        # Special case: "Fungicide And Nematicide" should be split into both categories
        if original_cat == 'Fungicide And Nematicide':
            if 'Fungicide' not in simplified_categories:
                simplified_categories.append('Fungicide')
            if 'Nematicide' not in simplified_categories:
                simplified_categories.append('Nematicide')
        else:
            simplified_cat = get_simplified_category(original_cat)
            if simplified_cat not in simplified_categories:
                simplified_categories.append(simplified_cat)
    
    return simplified_categories

if __name__ == "__main__":
    # Test the lookup table
    print("🧪 Testing pesticide category lookup...")
    
    # Test individual categories
    test_categories = ['Fungicide', 'Fungicide/Fungistat', 'Herbicide Terrestrial', 'Fungicide And Nematicide']
    for cat in test_categories:
        simplified = get_simplified_category(cat)
        print(f"   {cat} → {simplified}")
    
    # Test comma-separated categories
    test_string = "Antimicrobial, Bacteriocide, Disinfectant, Fungicide, Sanitizer, Tuberculocide, Virucide"
    simplified_list = get_categories_for_pesticide(test_string)
    print(f"\n   Multi-category: {test_string}")
    print(f"   Simplified: {', '.join(simplified_list)}")
    
    # Show all simplified categories
    all_categories = get_all_simplified_categories()
    print(f"\n📊 Total simplified categories: {len(all_categories)}")
    print("   Categories:", ', '.join(all_categories))
