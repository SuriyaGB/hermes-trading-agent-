import json
from pathlib import Path
from datetime import datetime
import pytz

def load_json(path: Path) -> dict:
    try:
        with open(path, 'r') as f: return json.load(f)
    except: return {}

def write_json(path: Path, data: dict):
    with open(path, 'w') as f: json.dump(data, f, indent=2)

def get_market_date(dt: datetime = None) -> str:
    if dt is None:
        dt = datetime.now()
    eastern = pytz.timezone("America/New_York")
    dt = dt.astimezone(eastern)
    return dt.strftime('%Y-%m-%d')

class ValidationError(ValueError):
    """Base exception for all Smart Guard validation gates."""
    pass

class PolicyBlockError(ValidationError):
    """Hard validation failure that halts execution."""
    pass

class PacingBlockError(ValidationError):
    """Soft validation failure that yields a HOLD override."""
    pass
