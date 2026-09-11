"""Configuration loader and validator for YAML configs."""
from pathlib import Path
from typing import Any, Dict
import yaml


class ConfigLoader:
    """Loads configuration files from the config directory."""

    def __init__(self, config_dir: str = "config"):
        self.config_path = Path(config_dir)

    def load_yaml(self, filename: str) -> Dict[str, Any]:
        """Loads and returns a YAML configuration file as a dict."""
        file_path = self.config_path / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data or {}

    @property
    def settings(self) -> Dict[str, Any]:
        """Returns the main settings dictionary."""
        return self.load_yaml("settings.yaml")

    @property
    def profiles(self) -> Dict[str, Any]:
        """Returns risk profiles dictionary."""
        return self.load_yaml("profiles.yaml")

    @property
    def strategies(self) -> Dict[str, Any]:
        """Returns strategies configuration dictionary."""
        return self.load_yaml("strategies.yaml")


# Global convenient singleton instance
config = ConfigLoader()
