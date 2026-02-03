"""
Prompt Manager module for versioned prompt loading.
Loads prompts from markdown files with YAML configuration.
"""

import yaml
from pathlib import Path
from typing import Dict, Optional

# Default prompts directory
_DEFAULT_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class PromptManager:
    """
    Manages versioned prompts stored as markdown files.
    Configuration is stored in prompt_config.yaml for tracking versions.
    """

    def __init__(self, prompts_dir: Optional[str] = None):
        """
        Initialize prompt manager.

        Args:
            prompts_dir: Path to prompts directory. Defaults to backend/prompts/
        """
        if prompts_dir is None:
            self.prompts_dir = _DEFAULT_PROMPTS_DIR
        else:
            self.prompts_dir = Path(prompts_dir)

        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Load prompt configuration from YAML file."""
        config_path = self.prompts_dir / "prompt_config.yaml"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            return {"prompts": {}, "metadata": {}}

    def load_prompt(self, prompt_name: str, version: str = "latest") -> str:
        """
        Load a prompt template from markdown file.

        Args:
            prompt_name: Name of the prompt (e.g., 'system_prompt')
            version: Version to load (e.g., 'v1') or 'latest' for most recent

        Returns:
            Prompt template as string
        """
        # Resolve 'latest' to actual version
        if version == "latest":
            prompt_config = self.config.get("prompts", {}).get(prompt_name, {})
            version = prompt_config.get("latest_version", "v1")

        filename = f"{prompt_name}_{version}.md"
        filepath = self.prompts_dir / filename

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Prompt file not found: {filepath}. "
                f"Please create {filename} in {self.prompts_dir}"
            )

    def render_prompt(self, prompt_name: str, version: str = "latest", **kwargs) -> str:
        """
        Load a prompt and render it with provided variables.

        Args:
            prompt_name: Name of the prompt
            version: Version to load
            **kwargs: Variables to substitute in the template

        Returns:
            Rendered prompt string
        """
        template = self.load_prompt(prompt_name, version)

        # Replace placeholders with provided values
        # Using format_map to handle missing keys gracefully
        class SafeDict(dict):
            def __missing__(self, key):
                return f"{{{key}}}"

        return template.format_map(SafeDict(**kwargs))

    def list_prompts(self) -> Dict:
        """
        List all available prompts and their versions.

        Returns:
            Dict of prompt names to version info
        """
        return self.config.get("prompts", {})

    def get_latest_version(self, prompt_name: str) -> str:
        """
        Get the latest version string for a prompt.

        Args:
            prompt_name: Name of the prompt

        Returns:
            Latest version string (e.g., 'v2')
        """
        prompt_config = self.config.get("prompts", {}).get(prompt_name, {})
        return prompt_config.get("latest_version", "v1")


# Global instance for easy access
prompt_manager = PromptManager()
