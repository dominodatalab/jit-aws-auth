"""
Provides a singleton mapping for retrieving settings values
"""
import json
from typing import Iterator, Mapping

base_path = ''
SETTINGS_FILE = base_path + '/etc/config/jit.properties'


# SETTINGS_FILE = '/domino/domsedjit/settings.json'


class Settings(Mapping[str, str]):
    """
    Implements a mapping that lazily loads settings from a local file
    """

    def __init__(self) -> None:
        super().__init__()
        self._settings_dict = {}

    def __getitem__(self, key: str) -> str:
        self._ensure_loaded()
        return self._settings_dict[key]

    def __iter__(self) -> Iterator[str]:
        self._ensure_loaded()
        return self._settings_dict.__iter__()

    def __len__(self) -> int:
        self._ensure_loaded()
        return len(self._settings_dict)

    def _ensure_loaded(self):
        if not self.loaded:
            with open(SETTINGS_FILE, 'r') as settings_fp:
                self._settings_dict = json.load(settings_fp)

    def __str__(self) -> str:
        return str(dict(self))

    @property
    def loaded(self) -> bool:
        """
        Indicates whether the local settings file has been loaded into
        memory

        Returns:
            bool: `True` if settings are loaded; `False` otherwise
        """
        return bool(self._settings_dict)


SETTINGS = Settings()
