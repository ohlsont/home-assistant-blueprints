"""Coordinator for Blockheat runtime state."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class BlockheatCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Hold latest Blockheat runtime snapshot."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(hass, logger=_LOGGER, name=DOMAIN)
