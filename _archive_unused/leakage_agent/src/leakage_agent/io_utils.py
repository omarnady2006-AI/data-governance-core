import pandas as pd
import json
import numpy as np
from pathlib import Path

class RobustEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer, np.floating, np.bool_, np.ndarray)):
            if isinstance(obj, np.bool_):
                return bool(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return obj.item()
        return super().default(obj)

def write_outputs(df, report, summary, decision, out_dir, copy_id):
    base_dir = Path(out_dir)
    base_dir.mkdir(exist_ok=True)
    for sub in ["cleaned", "quarantine", "reports", "summaries"]:
        (base_dir / sub).mkdir(parents=True, exist_ok=True)
    
    file_name = f"copy_{copy_id}.csv"
    json_name = f"copy_{copy_id}.json"
    
    with open(base_dir / "reports" / json_name, "w") as f:
        json.dump(report, f, indent=2, cls=RobustEncoder)
    with open(base_dir / "summaries" / json_name, "w") as f:
        json.dump(summary, f, indent=2, cls=RobustEncoder)
        
    if decision == "ACCEPT":
        df.to_csv(base_dir / "cleaned" / file_name, index=False)
    elif decision == "QUARANTINE":
        df.to_csv(base_dir / "quarantine" / file_name, index=False)
