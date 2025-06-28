import json
from datetime import datetime

# Load the JSON data
with open("response.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Convert timestamps
for entry in data:
    if "timestamp" in entry:
        # Convert to readable format (UTC)
        entry["datetime"] = datetime.utcfromtimestamp(entry["timestamp"]).strftime('%Y-%m-%d %H:%M:%S UTC')

# Save the updated data to a new file (optional)
with open("response_with_dates.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

# Or print the first entry as an example
print(json.dumps(data[0], indent=4))
