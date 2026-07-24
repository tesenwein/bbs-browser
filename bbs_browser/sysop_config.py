"""Configuration, pricing and pure helper functions for the AI SysOp.

Everything here is module-level state and pure functions that do not need
the SysOp class instance: provider/model configuration, key storage and
migration, pricing tables, shell-access config and prompt/persona helpers.
"""

import os

from . import vault
from .i18n import t
from .state import load_ai_config, load_section, save_ai_config, save_section

# Prices in dollars per 1 million tokens (input, output).
PRICES = {
    "haiku-4-5": (1.0, 5.0),
    "haiku-4.5": (1.0, 5.0),
    "sonnet-4-6": (3.0, 15.0),
    "sonnet-4.6": (3.0, 15.0),
    "sonnet-5": (3.0, 15.0),
    "opus-4-8": (5.0, 25.0),
    "opus-4.8": (5.0, 25.0),
    "deepseek-v4-flash": (0.14, 0.28),
    # OpenAI — longer names first, so 'gpt-4o-mini' matches before 'gpt-4o'.
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.0, 8.0),
    "gpt-4o": (2.5, 10.0),
}
DEFAULT_PRICE = (1.0, 5.0)  # like Haiku 4.5


def price_for(model):
    model = (model or "").lower()
    for name, price in PRICES.items():
        if name in model:
            return price
    return DEFAULT_PRICE


def estimate_cost(model, tokens_in, tokens_out):
    p_in, p_out = price_for(model)
    return (tokens_in * p_in + tokens_out * p_out) / 1_000_000

VERCEL_BASE_URL = "https://ai-gateway.vercel.sh"
DEFAULT_MODEL_ANTHROPIC = "claude-haiku-4-5"
DEFAULT_MODEL_VERCEL = "deepseek/deepseek-v4-flash"
DEFAULT_MODEL_OPENAI = "gpt-4o-mini"
MAX_PAGE_CHARS = 15000
MAX_AGENT_STEPS = 8  # upper bound for tool rounds per request
# The templater needs more rounds than a normal request: probing selectors,
# previewing, correcting — and it only runs ONCE per domain.
MAX_TEMPLATE_STEPS = 14
# The three selectable providers. 'anthropic' and 'vercel' share the
# anthropic SDK (Vercel is Anthropic-compatible), 'openai' has its own.
PROVIDERS = ("anthropic", "vercel", "openai")
DEFAULT_MODELS = {
    "anthropic": DEFAULT_MODEL_ANTHROPIC,
    "vercel": DEFAULT_MODEL_VERCEL,
    "openai": DEFAULT_MODEL_OPENAI,
}
ENV_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "vercel": "AI_GATEWAY_API_KEY",
    "openai": "OPENAI_API_KEY",
}


# -- System access (shell) ------------------------------------------------
#
# Off by default. When enabled in the config menu, the agent gets an
# additional tool; in "confirm" mode the caller must approve each command
# beforehand.
SHELL_MODES = ("off", "confirm", "free")
SHELL_DEFAULT_TIMEOUT = 30
MAX_SHELL_OUTPUT = 4000


def shell_config():
    """(mode, timeout) of system access — with safe defaults."""
    cfg = load_section("shell")
    mode = cfg.get("mode")
    if mode not in SHELL_MODES:
        mode = "off"
    try:
        timeout = int(cfg.get("timeout") or SHELL_DEFAULT_TIMEOUT)
    except (TypeError, ValueError):
        timeout = SHELL_DEFAULT_TIMEOUT
    return mode, max(1, timeout)


def shell_enabled():
    return shell_config()[0] != "off"


def provider_label(provider):
    """Translated label of a provider (for status and config menu)."""
    return {
        "anthropic": t("sysop.status_route_anthropic"),
        "vercel": t("sysop.status_route_vercel"),
        "openai": t("sysop.status_route_openai"),
    }.get(provider, provider)


def default_model(provider):
    return DEFAULT_MODELS.get(provider, DEFAULT_MODEL_ANTHROPIC)


def detect_provider(key):
    """Guess the provider from the key prefix — or None if ambiguous."""
    key = key or ""
    if key.startswith("vck_"):
        return "vercel"
    if key.startswith("sk-ant-"):
        return "anthropic"
    return None


def active_provider(cfg):
    """The currently selected provider from the config (with legacy-format fallback)."""
    provider = cfg.get("provider")
    if provider in PROVIDERS:
        return provider
    # Legacy format: only one 'api_key' — derive the provider from the prefix.
    return detect_provider(cfg.get("api_key", "")) or "anthropic"


def key_slot(provider):
    """Name of a provider's keyring slot."""
    return f"ai:{provider}"


def config_key(cfg, provider):
    """Stored key of a provider — from the keyring, from the DB
    (older versions), or from the legacy format with only one 'api_key'."""
    keys = cfg.get("keys") or {}
    if keys.get(provider):
        return vault.resolve(keys[provider], key_slot(provider))
    legacy = cfg.get("api_key", "")
    if legacy and (detect_provider(legacy) or active_provider(cfg)) == provider:
        return legacy
    return ""


def set_config_key(cfg, provider, key):
    """Stores a provider's key — preferably in the keyring, with only
    the marker left in the DB. Removes the legacy field in the process."""
    keys = dict(cfg.get("keys") or {})
    stored = vault.store(key, key_slot(provider))
    if stored:
        keys[provider] = stored
    else:
        keys.pop(provider, None)
    cfg["keys"] = keys
    # Any existing legacy field now belongs to 'keys' — don't keep it twice.
    cfg.pop("api_key", None)
    return cfg


FIRECRAWL_SLOT = "firecrawl"


def migrate_keys():
    """One-time: move plaintext keys from the DB into the keyring.

    Runs at startup. Without a usable keyring nothing happens, then everything
    stays in the DB as before."""
    if not vault.available():
        return
    cfg = load_ai_config()
    changed = False
    # Lift the legacy format (a single 'api_key') into the 'keys' format first.
    legacy = cfg.get("api_key", "")
    if legacy:
        keys = dict(cfg.get("keys") or {})
        keys.setdefault(detect_provider(legacy) or active_provider(cfg), legacy)
        cfg["keys"], changed = keys, True
        cfg.pop("api_key", None)
    for provider, value in list((cfg.get("keys") or {}).items()):
        if value and value != vault.MARK and vault.put(key_slot(provider), value):
            cfg["keys"][provider] = vault.MARK
            changed = True
    if changed:
        save_ai_config(cfg)

    fc = load_section("firecrawl")
    if fc.get("api_key") and fc["api_key"] != vault.MARK:
        if vault.put(FIRECRAWL_SLOT, fc["api_key"]):
            fc["api_key"] = vault.MARK
            save_section("firecrawl", fc)


def firecrawl_key(fc):
    """Firecrawl key from config or keyring, otherwise from the environment."""
    stored = vault.resolve(fc.get("api_key", ""), FIRECRAWL_SLOT)
    return stored or os.environ.get("FIRECRAWL_API_KEY", "")


def set_firecrawl_key(fc, key):
    fc["api_key"] = vault.store(key, FIRECRAWL_SLOT)
    return fc


def custom_prompt():
    """The caller's stored default prompt (config menu 'c')."""
    return (load_ai_config().get("prompt") or "").strip()


def persona():
    """SysOp system prompt: the fixed role, plus the caller's additional
    instructions, if they set a default prompt in the config menu."""
    base = t("sysop.persona")
    extra = custom_prompt()
    if extra:
        return base + "\n\n" + t("sysop.persona_custom_header") + "\n" + extra
    return base


def tool_label(name):
    """Human-readable description of a tool; falls back to the tool name.
    MCP tools ('server__tool') get a readable 'MCP server: tool' label."""
    key = "sysop.tool." + name
    label = t(key)
    if label != key:
        return label
    if "__" in name:
        server, _, tool = name.partition("__")
        return t("sysop.tool.mcp", server=server, tool=tool.replace("_", " "))
    return name.replace("_", " ")
