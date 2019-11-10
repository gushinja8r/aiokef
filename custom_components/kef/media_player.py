"""Platform for the KEF Wireless Speakers."""

import logging

import voluptuous as vol
from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
    MediaPlayerDevice,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, STATE_OFF, STATE_ON
from homeassistant.helpers import config_validation as cv

from custom_components.kef.async_kef_api import INPUT_SOURCES, AsyncKefSpeaker

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)


DEFAULT_NAME = "KEF"
DEFAULT_PORT = 50001
DEFAULT_MAX_VOLUME = 0.5
DEFAULT_VOLUME_STEP = 0.05
DATA_KEF = "kef"

SCAN_INTERVAL = 15  # Used in HA.

KEF_LS50_SOURCES = sorted(INPUT_SOURCES.keys())

SUPPORT_KEF = (
    SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_TURN_OFF
    | SUPPORT_TURN_ON
)

CONF_MAX_VOLUME = "maximum_volume"
CONF_VOLUME_STEP = "volume_step"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MAX_VOLUME, default=DEFAULT_MAX_VOLUME): cv.small_float,
        vol.Optional(CONF_VOLUME_STEP, default=DEFAULT_VOLUME_STEP): cv.small_float,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Setup Kef platform."""
    if DATA_KEF not in hass.data:
        hass.data[DATA_KEF] = {}

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)
    maximum_volume = config.get(CONF_MAX_VOLUME)
    volume_step = config.get(CONF_VOLUME_STEP)

    _LOGGER.debug(
        f"Setting up {DATA_KEF} with host: {host}, port: {port},"
        f" name: {name}, sources: {KEF_LS50_SOURCES}"
    )

    media_player = KefMediaPlayer(
        name,
        host,
        port,
        maximum_volume=maximum_volume,
        volume_step=volume_step,
        sources=KEF_LS50_SOURCES,
        hass=hass,
    )
    unique_id = f"{host}:{port}"
    if unique_id in hass.data[DATA_KEF]:
        _LOGGER.debug(f"{unique_id} is already configured.")
    else:
        hass.data[DATA_KEF][unique_id] = media_player
        async_add_entities([media_player], True)


class KefMediaPlayer(MediaPlayerDevice):
    """Kef Player Object."""

    def __init__(self, name, host, port, maximum_volume, volume_step, sources, hass):
        """Initialize the media player."""
        self._name = name
        self._hass = hass
        self._sources = sources
        self._speaker = AsyncKefSpeaker(
            host, port, volume_step, maximum_volume, ioloop=self._hass.loop
        )

        # Set internal states to None.
        self._state = None
        self._muted = None
        self._source = None
        self._volume = None

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    async def async_update(self):
        """Update latest state."""
        _LOGGER.debug("Running async_update")
        try:
            is_online = await self._speaker.is_online()
            if is_online:
                self._muted = await self._speaker.is_muted()
                self._volume = await self._speaker.get_volume()
                self._source, is_on = await self._speaker.get_source_and_state()
                self._state = STATE_ON if is_on else STATE_OFF
            else:
                self._muted = None
                self._source = None
                self._volume = None
                self._state = STATE_OFF
        except Exception as e:
            _LOGGER.debug(f"Error in `update`: {e}")

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_KEF

    @property
    def source(self):
        """Name of the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._sources

    async def async_turn_off(self):
        """Turn the media player off."""
        await self._speaker.turn_off()
        self._state = STATE_ON

    async def async_turn_on(self):
        """Turn the media player on."""
        await self._speaker.turn_on()
        self._state = STATE_OFF

    async def async_volume_up(self):
        """Volume up the media player."""
        self._volume = await self._speaker.increase_volume()

    async def async_volume_down(self):
        """Volume down the media player."""
        self._volume = await self._speaker.decrease_volume()

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        await self._speaker.set_volume(volume)
        self._volume = volume

    async def async_mute_volume(self, mute):
        """Mute (True) or unmute (False) media player."""
        if mute:
            await self._speaker.mute()
        else:
            await self._speaker.unmute()
        self._muted = mute

    async def async_select_source(self, source: str):
        """Select input source."""
        if source in self.source_list:
            self._source = source
            await self._speaker.set_source(source)
        else:
            raise ValueError(f"Unknown input source: {source}.")
