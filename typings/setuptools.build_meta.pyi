from typing import Any, Optional

def build_wheel(
    wheel_directory: str,
    config_settings: Optional[dict[Any, Any]] = None,
    metadata_directory: Optional[str] = None,
) -> str: ...
def build_sdist(
    sdist_directory: str, config_settings: Optional[dict[Any, Any]] = None
) -> str: ...
def build_editable(
    wheel_directory: str,
    config_settings: Optional[dict[Any, Any]] = None,
    metadata_directory: Optional[str] = None,
) -> str: ...
