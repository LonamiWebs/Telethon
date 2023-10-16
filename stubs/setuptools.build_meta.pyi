from typing import Any, Dict, Optional

def build_wheel(
    wheel_directory: str,
    config_settings: Optional[Dict[Any, Any]] = None,
    metadata_directory: Optional[str] = None,
) -> str: ...
def build_sdist(
    sdist_directory: str, config_settings: Optional[Dict[Any, Any]] = None
) -> str: ...
def build_editable(
    wheel_directory: str,
    config_settings: Optional[Dict[Any, Any]] = None,
    metadata_directory: Optional[str] = None,
) -> str: ...
