from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from duckdome.stores.settings_store import SettingsStore
from duckdome.services.wrapper_service import WrapperService

router = APIRouter(prefix="/api/settings", tags=["settings"])

_store: SettingsStore | None = None
_wrapper_service: WrapperService | None = None


def init(store: SettingsStore, wrapper_service: WrapperService | None = None) -> None:
    global _store, _wrapper_service
    _store = store
    _wrapper_service = wrapper_service


def _get_store() -> SettingsStore:
    if _store is None:
        raise RuntimeError("Settings router is not initialized")
    return _store


class SettingsPatch(BaseModel):
    show_agent_windows: bool | None = None


@router.get("", status_code=200)
def get_settings():
    return _get_store().get_all()


@router.patch("", status_code=200)
def patch_settings(body: SettingsPatch):
    store = _get_store()
    if body.show_agent_windows is not None:
        if _wrapper_service is not None:
            _wrapper_service.set_show_windows(body.show_agent_windows)
        store.set("show_agent_windows", body.show_agent_windows)
    return store.get_all()
