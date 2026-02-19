"""Coordinator for Blockheat runtime state."""

from __future__ import annotations

from typing import Any
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class BlockheatCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Hold latest Blockheat runtime snapshot."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(hass, logger=_LOGGER, name=DOMAIN)
