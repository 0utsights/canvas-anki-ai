import importlib
from concurrent.futures import Future
from typing import Any, Mapping, Tuple


PUBLIC_MODULE_NAME = "anki_ai_bridge_api"
REQUIRED_API_MAJOR = "1"


class AnkiAIBridgeUnavailable(RuntimeError):
    pass


class AnkiAIBridgeClient:
    def __init__(self, consumer_id: str) -> None:
        if not consumer_id.strip():
            raise ValueError("consumer_id is required")
        self.consumer_id = consumer_id

    def list_providers(self) -> Tuple[Mapping[str, Any], ...]:
        return self._api().list_providers()

    def complete_json(
        self, provider: str, task: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return self._api().complete_json(self.consumer_id, provider, dict(task))

    def submit_json(self, provider: str, task: Mapping[str, Any]) -> Future:
        return self._api().submit_json(self.consumer_id, provider, dict(task))

    @staticmethod
    def _api():
        try:
            api = importlib.import_module(PUBLIC_MODULE_NAME)
        except ImportError as error:
            raise AnkiAIBridgeUnavailable(
                "Install and enable the Anki AI Bridge add-on, then restart Anki."
            ) from error
        version = str(getattr(api, "API_VERSION", "0"))
        if version.split(".", 1)[0] != REQUIRED_API_MAJOR:
            raise AnkiAIBridgeUnavailable(
                f"Anki AI Bridge API {version} is incompatible with required major "
                f"version {REQUIRED_API_MAJOR}."
            )
        return api
