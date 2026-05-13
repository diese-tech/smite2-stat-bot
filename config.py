import json
import os
import tempfile

from dotenv import load_dotenv

load_dotenv()

# ── Railway / hosted environment: credentials JSON stored as env var ───────
# On Railway, you can't upload files directly. Instead, paste the entire
# contents of your credentials JSON file into a Railway env var called
# GOOGLE_CREDENTIALS_JSON. This block writes it to a temp file at startup.
_creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
if _creds_json:
    _tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(json.loads(_creds_json), _tmp)
    _tmp.close()
    os.environ["GOOGLE_CREDENTIALS_PATH"] = _tmp.name

# ── League identity ────────────────────────────────────────────────────────
LEAGUE_NAME = "Frank's Retirement Home"
LEAGUE_SLUG = "franks-retirement-home"
LEAGUE_PREFIX = os.getenv("LEAGUE_PREFIX", "FRH")  # used by /newmatch for non-GodForge servers

# ── Discord ────────────────────────────────────────────────────────────────
def _optional_int(name: str) -> int | None:
    value = os.getenv(name)
    return int(value) if value else None


DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SCREENSHOT_CHANNEL_ID = _optional_int("SCREENSHOT_CHANNEL_ID")
JSON_CHANNEL_ID = _optional_int("JSON_CHANNEL_ID")
ADMIN_REPORT_CHANNEL_ID = _optional_int("ADMIN_REPORT_CHANNEL_ID")
STAFF_ROLE_IDS = [int(rid.strip()) for rid in os.getenv("STAFF_ROLE_IDS", "").split(",") if rid.strip()]
STAT_ADMIN_USER_IDS = [
    int(uid.strip()) for uid in os.getenv("STAT_ADMIN_USER_IDS", "").split(",") if uid.strip()
]
CONFIDENCE_THRESHOLD = int(os.getenv("CONFIDENCE_THRESHOLD", "90"))
BETTING_ENABLED = os.getenv("BETTING_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
STARTING_BALANCE = int(os.getenv("STARTING_BALANCE", "500"))
FORGELENS_ECONOMY_PATH = os.getenv("FORGELENS_ECONOMY_PATH", "").strip()
FORGELENS_MATCHES_PATH = os.getenv("FORGELENS_MATCHES_PATH", "").strip()

# ── Google ─────────────────────────────────────────────────────────────────
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "franks-retirement-home-credentials.json")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PARENT_DRIVE_FOLDER_ID = os.getenv("PARENT_DRIVE_FOLDER_ID") or None
