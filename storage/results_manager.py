# storage/results_manager.py
"""Save and load favorite backtest results as JSON"""

import os
import json
from datetime import datetime
from config import RESULTS_DIR

os.makedirs(RESULTS_DIR, exist_ok=True)


def save_result(name, config, metrics):
    """Save a backtest result the user likes."""
    record = {
        "name": name,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "config": config,
        "metrics": metrics,
    }
    filename = f"{name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path = os.path.join(RESULTS_DIR, filename)
    with open(path, "w") as f:
        json.dump(record, f, indent=2, default=str)
    return path


def load_all_results():
    results = []
    for file in os.listdir(RESULTS_DIR):
        if file.endswith(".json"):
            with open(os.path.join(RESULTS_DIR, file)) as f:
                data = json.load(f)
                data["_file"] = file
                results.append(data)
    return sorted(results, key=lambda x: x.get("saved_at", ""), reverse=True)


def delete_result(filename):
    path = os.path.join(RESULTS_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False
