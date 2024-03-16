from typing import Any, Dict, Optional

class build_meta:
    @staticmethod
    def build_wheel(
        wheel_directory: str,
        config_settings: Optional[Dict[Any, Any]] = None,
        metadata_directory: Optional[str] = None,
    ) -> str: ...
    @staticmethod
    def build_sdist(
        sdist_directory: str, config_settings: Optional[Dict[Any, Any]] = None
    ) -> str: ...
    @staticmethod
    def build_editable(
        wheel_directory: str,
        config_settings: Optional[Dict[Any, Any]] = None,
        metadata_directory: Optional[str] = None,
    ) -> str: ...
