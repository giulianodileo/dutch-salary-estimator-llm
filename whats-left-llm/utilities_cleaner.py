# ---------- LIBRARIES ---------- #

import json
import os

# ---------- UPDATE DATA PERIOD ---------- #


def update_period(data):
    """
    Replace 'per month' with 'monthly' in the 'period' field.
    """
    for item in data:
        if item.get("period") == "per month":
            item["period"] = "monthly"
    return data


# ---------- SAVE UPDATES TO JSON FILE ---------- #


def save_to_json(data, filepath="data/clean_utilities.json"):
    """
    Save the given data to a JSON file at the specified filepath.
    Creates the directory if it doesn't exist.
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"File saved at: {filepath}")


# ---------- ADDS SOURCE SOTE ---------- #



def add_source_site(data, site_name="nibud"):
    """
    Add a 'source_site' key to each item in the dataset.
    By default, sets site_name='nibud'.
    """
    for item in data:
        if "source_url" in item:
            item["source_site"] = site_name
    return data


# Example usage
if __name__ == "__main__":
    json_data = [
        {
            "category": "Gas",
            "value": 110.0,
            "period": "per month",
            "year": 2025,
            "source_url": "https://www.nibud.nl/onderwerpen/uitgaven/kosten-energie-water/"
        },
        {
            "category": "Electricity",
            "value": 54.5,
            "period": "per month",
            "year": 2025,
            "source_url": "https://www.nibud.nl/onderwerpen/uitgaven/kosten-energie-water/"
        },
        {
            "category": "Water",
            "value": 25.9,
            "period": "per month",
            "year": 2025,
            "source_url": "https://www.nibud.nl/onderwerpen/uitgaven/kosten-energie-water/"
        }
    ]


# ---------- APPLIES TRANSFORMATION AND SAVE INTO NEW JSON ---------- #


    # Apply transformations
    updated_data = update_period(json_data)
    updated_data = add_source_site(updated_data)

    # Save result
    save_to_json(updated_data)
