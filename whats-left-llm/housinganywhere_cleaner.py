import json

def transform_data_with_ranges(data: list) -> list:
    """
    Transform housing data with the following rules:
    - Keep only items where accommodation == "Room"
    - Rename 'current_quarter' to 'avg_price'
    - Remove unwanted keys
    - Add 'min_price' and 'max_price' using ±25% of avg
    - Round to whole numbers
    - Add 'source_url' and 'source_site'
    """
    transformed = []

    for item in data:
        if item.get("accommodation") == "Room":
            avg_price = float(item["current_quarter"])
            new_item = {
                "city": item["city"],
                "accommodation": item["accommodation"],
                "period": item["period"],
                "currency": item["currency"],
                "min_price": float(round(avg_price * 0.75)),  # -25%
                "avg_price": float(round(avg_price)),
                "max_price": float(round(avg_price * 1.25)),  # +25%
                "source_url": "https://housinganywhere.com/rent-index-by-city",
                "source_site": "HousingAnywhere"
            }
            transformed.append(new_item)

    return transformed


# Example usage with your JSON
if __name__ == "__main__":
    raw_data = [
      {
        "city": "Amsterdam",
        "accommodation": "Apartment",
        "period": "monthly",
        "currency": "EUR",
        "current_quarter": 2685.0,
        "previous_quarter": 2500.0,
        "last_year": 2500.0,
        "change_vs_prev": 7.4,
        "change_vs_year": 7.4
      },
      {
        "city": "Amsterdam",
        "accommodation": "Room",
        "period": "monthly",
        "currency": "EUR",
        "current_quarter": 969.0,
        "previous_quarter": 971.0,
        "last_year": 1000.0,
        "change_vs_prev": -0.2,
        "change_vs_year": -3.1
      },
      {
        "city": "Rotterdam",
        "accommodation": "Room",
        "period": "monthly",
        "currency": "EUR",
        "current_quarter": 825.0,
        "previous_quarter": 850.0,
        "last_year": 850.0,
        "change_vs_prev": -2.9,
        "change_vs_year": -2.9
      },
      {
        "city": "The Hague",
        "accommodation": "Room",
        "period": "monthly",
        "currency": "EUR",
        "current_quarter": 850.0,
        "previous_quarter": 900.0,
        "last_year": 875.0,
        "change_vs_prev": -5.6,
        "change_vs_year": -2.9
      }
    ]

    result = transform_data_with_ranges(raw_data)
    print(json.dumps(result, indent=2))
