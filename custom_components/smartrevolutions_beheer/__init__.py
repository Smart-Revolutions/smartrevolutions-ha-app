"""Smartrevolutions beheer: allowlisted, time-limited support account access."""
from datetime import datetime, timedelta, timezone
import logging
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.storage import Store
from homeassistant.exceptions import HomeAssistantError

DOMAIN = "smartrevolutions_beheer"
_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({
    vol.Required("support_user_id"): cv.string,
    vol.Required("allowed_user_ids"): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional("max_minutes", default=1440): vol.All(vol.Coerce(int), vol.Range(min=1, max=10080)),
})}, extra=vol.ALLOW_EXTRA)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    if DOMAIN not in config:
        return True
    settings = config[DOMAIN]
    support_id = settings["support_user_id"]
    allowed = set(settings["allowed_user_ids"])
    if support_id in allowed or not allowed:
        raise HomeAssistantError("Configure at least one allowed user, distinct from the support account")
    support = await hass.auth.async_get_user(support_id)
    if support is None or support.is_owner or support.system_generated or not support.is_admin:
        raise HomeAssistantError("Support account must be an existing non-owner administrator")
    for uid in allowed:
        if await hass.auth.async_get_user(uid) is None:
            raise HomeAssistantError(f"Unknown allowed user ID: {uid}")
    store = Store(hass, 1, DOMAIN)
    state = await store.async_load() or {}
    cancel = None
    expires = None

    async def disable():
        nonlocal cancel, expires
        if cancel:
            cancel()
            cancel = None
        user = await hass.auth.async_get_user(support_id)
        if user and user.is_active:
            await hass.auth.async_deactivate_user(user)
        expires = None
        await store.async_save({"expires": None})
        hass.bus.async_fire(f"{DOMAIN}_changed", {"active": False})
        _LOGGER.info("Support account disabled")

    @callback
    def schedule(end: datetime):
        nonlocal cancel, expires
        if cancel:
            cancel()
        expires = end
        async def expire(_now):
            await disable()
        cancel = async_track_point_in_utc_time(hass, expire, end)

    raw = state.get("expires")
    if raw:
        try:
            end = datetime.fromisoformat(raw)
            if end.tzinfo is None:
                raise ValueError("Naive datetime")
            if end > datetime.now(timezone.utc) and support.is_active:
                schedule(end)
            else:
                await disable()
        except (ValueError, TypeError):
            await disable()
    elif support.is_active:
        # Fail closed: never leave support enabled without a managed expiry.
        await disable()

    def authorize(call: ServiceCall):
        if not call.context.user_id or call.context.user_id not in allowed:
            raise HomeAssistantError("Not authorized to manage support access")

    async def activate(call: ServiceCall):
        authorize(call)
        minutes = call.data["minutes"]
        if minutes > settings["max_minutes"]:
            raise HomeAssistantError("Requested duration exceeds configured maximum")
        user = await hass.auth.async_get_user(support_id)
        if user is None or user.is_owner or not user.is_admin:
            raise HomeAssistantError("Support account is missing or no longer an administrator")
        end = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        # Persist deadline before enabling access, so a restart can recover it.
        await store.async_save({"expires": end.isoformat()})
        try:
            await hass.auth.async_activate_user(user)
        except Exception:
            await store.async_save({"expires": None})
            raise
        schedule(end)
        hass.bus.async_fire(f"{DOMAIN}_changed", {"active": True, "expires": end.isoformat()})
        _LOGGER.info("Support account enabled for %s minutes by %s", minutes, call.context.user_id)

    async def revoke(call: ServiceCall):
        authorize(call)
        await disable()
        _LOGGER.info("Support access revoked by %s", call.context.user_id)

    hass.services.async_register(DOMAIN, "activate", activate, schema=vol.Schema({vol.Required("minutes"): vol.All(vol.Coerce(int), vol.Range(min=1, max=10080))}))
    hass.services.async_register(DOMAIN, "revoke", revoke, schema=vol.Schema({}))
    return True
