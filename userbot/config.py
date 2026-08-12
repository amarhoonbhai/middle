import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

class Config:
    """Handles parsing and validating the configuration variables."""
    
    def __init__(self) -> None:
        self.API_ID: int = self._get_required_int("API_ID")
        self.API_HASH: str = self._get_required_str("API_HASH")
        self.SESSION_NAME: str = os.getenv("SESSION_NAME", "userbot_session")
        self.OWNER_ID: int = self._get_required_int("OWNER_ID")

    def _get_required_str(self, var_name: str) -> str:
        val = os.getenv(var_name)
        if not val or not val.strip():
            raise ValueError(f"Configuration error: '{var_name}' environment variable is missing or empty.")
        return val.strip()

    def _get_required_int(self, var_name: str) -> int:
        val_str = self._get_required_str(var_name)
        try:
            return int(val_str)
        except ValueError:
            raise ValueError(f"Configuration error: '{var_name}' must be a valid integer. Got: '{val_str}'")

# Initialize configuration singleton
config = Config()
