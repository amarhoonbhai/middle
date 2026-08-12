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
        self.OWNER_ID = None
        owner_id_str = os.getenv("OWNER_ID")
        if owner_id_str and owner_id_str.strip():
            try:
                self.OWNER_ID = int(owner_id_str)
            except ValueError:
                raise ValueError(f"Configuration error: 'OWNER_ID' must be a valid integer. Got: '{owner_id_str}'")

        # Optional Proxy Configurations
        self.PROXY_IP = os.getenv("PROXY_IP")
        proxy_port_str = os.getenv("PROXY_PORT")
        self.PROXY_PORT = int(proxy_port_str) if proxy_port_str and proxy_port_str.strip() else None
        self.PROXY_USER = os.getenv("PROXY_USER")
        self.PROXY_PASS = os.getenv("PROXY_PASS")

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
