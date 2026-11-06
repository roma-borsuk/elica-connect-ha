"""Fan platform for Elica Connect (hood motor)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import (
    DOMAIN,
    MANUFACTURER,
    CAP_FAN_SPEED,
    CAP_FAN_MODE,
    FAN_CMD,
    FAN_SPEED_BOOST,
    FAN_SPEED_COUNT,
    PRESET_BOOST,
)
from .coordinator import ElicaConnectCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ElicaConnectCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ElicaHoodFan(coordinator, entry)])


class ElicaHoodFan(CoordinatorEntity, FanEntity):
    """Elica hood fan.

    The hood has 3 normal speeds, exposed as percentages (33/66/100),
    plus a separate boost (intensive) mode exposed as a preset:
      0 = off            → {64:1, 110:0}
      1 = low    (33%)   → {64:1, 110:1}
      2 = medium (66%)   → {64:1, 110:2}
      3 = high   (100%)  → {64:1, 110:3}
      preset "boost"     → {64:4}
    """

    _attr_has_entity_name = True
    _attr_name = "Fan"
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_preset_modes = [PRESET_BOOST]
    _attr_speed_count = FAN_SPEED_COUNT

    def __init__(self, coordinator: ElicaConnectCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.data['device_id']}_fan"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.data["device_id"])},
            "name": coordinator.device_name,
            "manufacturer": MANUFACTURER,
            "model": "Elica Connect Hood",
            "serial_number": entry.data["device_id"],
        }
        self._optimistic_speed: int | None = None

    def _handle_coordinator_update(self) -> None:
        self._optimistic_speed = None
        super()._handle_coordinator_update()

    @property
    def _caps(self) -> dict:
        return self.coordinator.data or {}

    @property
    def _current_speed(self) -> int:
        """Return current speed: 0=off, 1-3=normal, FAN_SPEED_BOOST=boost."""
        if self._optimistic_speed is not None:
            return self._optimistic_speed
        if self._caps.get(CAP_FAN_MODE) == 4:
            return FAN_SPEED_BOOST
        return self._caps.get(CAP_FAN_SPEED, 0)

    @property
    def is_on(self) -> bool:
        return self._current_speed > 0

    @property
    def percentage(self) -> int | None:
        speed = self._current_speed
        if speed == FAN_SPEED_BOOST:
            return 100
        if speed <= 0:
            return 0
        return ranged_value_to_percentage((1, FAN_SPEED_COUNT), speed)

    @property
    def preset_mode(self) -> str | None:
        return PRESET_BOOST if self._current_speed == FAN_SPEED_BOOST else None

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
            return
        speed = self._pct_to_speed(percentage) if percentage is not None else 1
        await self._send(speed)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._send(0)

    async def async_set_percentage(self, percentage: int) -> None:
        await self._send(self._pct_to_speed(percentage))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode != PRESET_BOOST:
            raise ValueError(f"Unsupported preset mode: {preset_mode}")
        await self._send(FAN_SPEED_BOOST)

    async def _send(self, speed: int) -> None:
        self._optimistic_speed = speed
        self.async_write_ha_state()
        caps = FAN_CMD[speed]
        await self.coordinator.api.async_send_command(self.coordinator.device_id, caps)

    @staticmethod
    def _pct_to_speed(pct: int) -> int:
        if pct <= 0:
            return 0
        return max(1, min(FAN_SPEED_COUNT, round(percentage_to_ranged_value((1, FAN_SPEED_COUNT), pct))))
