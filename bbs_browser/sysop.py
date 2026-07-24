"""AI SysOp: an agent with internal tools.

The SysOp is a tool-use agent: the browser exposes its capabilities as
internal tools (read page, list links, follow link, dial URL, search,
Firecrawl scrape), and Claude decides for itself which ones to use.
'sum', 'ask <question>', 'go <text>' and 'chat' are just different orders to
the same agent.

Three providers are available; the caller switches with 'ai provider <name>'
or in the config menu ('c'). Each provider stores its own key:
    anthropic = Anthropic direct   (sk-ant-...)   full capabilities incl. Firecrawl MCP
    vercel    = Vercel AI Gateway  (vck_...)      Anthropic-compatible, no MCP scrape
    openai    = OpenAI direct       (sk-...)       own SDK, no MCP scrape
Store a key with 'ai key <key>' (sets it for the active provider; vck_/sk-ant-
switch the provider automatically). Default model per provider:
Claude Haiku 4.5, DeepSeek V4 Flash (Vercel) resp. GPT-4o mini.
"""

import json
import os
import subprocess

from . import db, vault
from .i18n import t
from .state import load_ai_config, load_section, save_ai_config, save_section

CHAT_CHANNEL = "sysop"   # channel prefix of the SysOp chats in history
CHAT_TITLE_MAX = 40      # a chat title never grows past this
REPLAY_LINES = 6         # transcript lines shown when re-entering a chat

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


def _chat_when(ts):
    """Short timestamp for the chat board."""
    import time
    try:
        return time.strftime("%d.%m. %H:%M", time.localtime(ts))
    except (TypeError, ValueError, OSError):
        return "?"


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


class _ParagraphStream:
    """Renders streamed reply text paragraph by paragraph, so the answer
    appears while it is still being generated. Open code fences hold the
    flush back, so markdown never breaks mid-block."""

    def __init__(self, emit):
        self._emit = emit
        self._buf = ""

    def feed(self, delta):
        self._buf += delta or ""
        while True:
            cut = self._flush_point()
            if cut is None:
                return
            chunk, self._buf = self._buf[:cut], self._buf[cut:]
            if chunk.strip():
                self._emit(chunk)

    def _flush_point(self):
        start = 0
        while True:
            idx = self._buf.find("\n\n", start)
            if idx < 0:
                return None
            if self._buf[:idx].count("```") % 2 == 0:
                return idx + 2
            start = idx + 2

    def close(self):
        if self._buf.strip():
            self._emit(self._buf)
        self._buf = ""


def _anthropic_tool_defs(registry):
    """Converts the tool registry to Anthropic format (input_schema)."""
    return [
        {"name": tool["name"], "description": tool["description"],
         "input_schema": tool["parameters"]}
        for tool in registry
    ]


def _plain_blocks(content):
    """Reduces SDK response blocks to plain dicts with only the fields the
    Messages API accepts. Replaying the pydantic objects verbatim carries
    extra null fields (e.g. citations) that strict gateways such as the
    Vercel AI gateway reject with 400 'Invalid input'. Empty text blocks
    are dropped for the same reason."""
    blocks = []
    for block in content:
        btype = getattr(block, "type", None)
        if btype == "text":
            if block.text:
                blocks.append({"type": "text", "text": block.text})
        elif btype == "tool_use":
            blocks.append({"type": "tool_use", "id": block.id,
                           "name": block.name, "input": block.input or {}})
    return blocks


def _openai_tool_defs(registry):
    """Converts the tool registry to OpenAI format (function/parameters)."""
    return [
        {"type": "function", "function": {
            "name": tool["name"], "description": tool["description"],
            "parameters": tool["parameters"]}}
        for tool in registry
    ]


class _NormalizedUsage:
    """Normalizes OpenAI's usage numbers to Anthropic's field names,
    so SysOp.track() can count both providers the same way."""

    def __init__(self, prompt_tokens=0, completion_tokens=0):
        self.input_tokens = prompt_tokens or 0
        self.output_tokens = completion_tokens or 0
        self.cache_creation_input_tokens = 0
        self.cache_read_input_tokens = 0


class _UsageCarrier:
    def __init__(self, usage):
        self.usage = usage


def _openai_usage(resp):
    """Wraps an OpenAI response's usage into a track()-compatible object."""
    usage = getattr(resp, "usage", None)
    if usage is None:
        return _UsageCarrier(None)
    return _UsageCarrier(_NormalizedUsage(
        getattr(usage, "prompt_tokens", 0),
        getattr(usage, "completion_tokens", 0),
    ))


class SysOp:
    def __init__(self, term, browser=None):
        self.term = term
        self.browser = browser
        self._client = None
        self._provider = None
        self._model = None
        # History survives the session: it comes from the database and
        # is also appended there. Several chats exist side by side
        # (channels "sysop", "sysop:2", ...); the last one used is resumed.
        self.chat_channel = db.active_chat() or CHAT_CHANNEL
        if not self.chat_channel.startswith(CHAT_CHANNEL):
            self.chat_channel = CHAT_CHANNEL
        self.chat_history = db.chat_history(self.chat_channel, limit=20)
        self._chat_ctx_url = None  # page last given to the chat as context
        self._titled = set()       # channels already auto-titled this session
        self._reply_prefix = None  # compact label instead of a rule line (chat mode)
        self.session_usage = {"input": 0, "output": 0, "calls": 0}

    # -- Token usage -------------------------------------------------

    def track(self, resp):
        """Counts a response's tokens — for the session and persistently."""
        usage = getattr(resp, "usage", None)
        if usage is None:
            return
        fresh = getattr(usage, "input_tokens", 0) or 0
        cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        tokens_in = fresh + cache_write + cache_read
        tokens_out = getattr(usage, "output_tokens", 0) or 0
        if not tokens_in and not tokens_out:
            return
        # For cost purposes, cache tokens don't count at the full input price:
        # writing costs 1.25x, reading only 0.1x of the input price.
        billable_in = fresh + 1.25 * cache_write + 0.1 * cache_read
        self.session_usage["input"] += tokens_in
        self.session_usage["output"] += tokens_out
        self.session_usage["calls"] += 1
        total = load_section("usage")
        total["input"] = total.get("input", 0) + tokens_in
        total["output"] = total.get("output", 0) + tokens_out
        total["calls"] = total.get("calls", 0) + 1
        total["cost"] = total.get("cost", 0.0) + estimate_cost(self._model, billable_in, tokens_out)
        save_section("usage", total)

    def show_usage(self):
        """Command 'u': token usage and estimated costs."""
        term = self.term
        _, _, _, model = self._resolve()
        model = self._model or model or "(kein Modell)"
        s = self.session_usage
        total = load_section("usage")
        p_in, p_out = price_for(model)

        term.rule(t("sysop.usage_title"))
        term.type_out(t("sysop.usage_model_line", model=model, price_in=p_in, price_out=p_out), delay=0.002)
        rows = [
            (t("sysop.usage_session"), s["calls"], s["input"], s["output"],
             estimate_cost(model, s["input"], s["output"])),
            (t("sysop.usage_total"), total.get("calls", 0), total.get("input", 0),
             total.get("output", 0), total.get("cost", 0.0)),
        ]
        term.type_out(f"  {'':<14}{t('sysop.usage_calls'):>7}{t('sysop.usage_input'):>10}{t('sysop.usage_output'):>10}{t('sysop.usage_cost'):>12}", delay=0.001)
        for label, calls, t_in, t_out, cost in rows:
            cents = cost * 100
            money = f"${cost:.2f}" if cents >= 100 else f"{cents:.2f} ct"
            term.type_out(f"  {label:<14}{calls:>7}{t_in:>10,}{t_out:>10,}{money:>12}", delay=0.001)
        term.type_out(t("sysop.usage_reset_hint"), delay=0.002)
        term.rule()

    def reset_usage(self):
        save_section("usage", {})
        self.session_usage = {"input": 0, "output": 0, "calls": 0}
        self.term.type_out(t("sysop.usage_reset"), delay=0.003)

    # -- Configuration ---------------------------------------------------

    def _resolve(self):
        """Returns (provider, api_key, base_url, model).

        The provider comes from the config; the key from the environment (ENV_KEYS)
        or the config. If no explicit choice is made and only one ENV key is
        set, its provider is used. Without a key, api_key is None."""
        cfg = load_ai_config()
        explicit = cfg.get("provider") if cfg.get("provider") in PROVIDERS else None
        provider = explicit or active_provider(cfg)
        key = os.environ.get(ENV_KEYS[provider]) or config_key(cfg, provider)
        if not key and not explicit:
            # No key for the default provider: if an ENV key of another one
            # is set, use it (so e.g. a plain AI_GATEWAY_API_KEY keeps working).
            for other in PROVIDERS:
                env_key = os.environ.get(ENV_KEYS[other])
                if env_key:
                    provider, key = other, env_key
                    break
        if not key:
            return provider, None, None, None
        base_url = VERCEL_BASE_URL if provider == "vercel" else None
        model = cfg.get("model") or default_model(provider)
        return provider, key, base_url, model

    def client(self):
        if self._client is not None:
            return self._client
        provider, key, base_url, model = self._resolve()
        if not key:
            self.term.error(t("sysop.error_offline_no_api_key"))
            return None
        if provider == "openai":
            try:
                import openai
            except ImportError:
                self.term.error(t("sysop.error_offline_missing_openai"))
                return None
            kwargs = {"api_key": key}
            if base_url:
                kwargs["base_url"] = base_url
            self._client = openai.OpenAI(**kwargs)
        else:
            try:
                import anthropic
            except ImportError:
                self.term.error(t("sysop.error_offline_missing_anthropic"))
                return None
            kwargs = {"api_key": key}
            if base_url:
                kwargs["base_url"] = base_url
            self._client = anthropic.Anthropic(**kwargs)
        self._provider = provider
        self._model = model
        return self._client

    def has_key(self):
        """Is a key stored? Silent — reports nothing to the screen."""
        return bool(self._resolve()[1])

    def model_name(self):
        """The active model — without building a client, '' as long as there's no key."""
        return self._model or self._resolve()[3] or ""

    def configure(self, arg):
        """Command 'ai': show status, set 'ai provider <name>' / 'ai key <key>' /
        'ai model <name>'."""
        term = self.term
        parts = arg.split(None, 1)
        if parts and parts[0] == "provider" and len(parts) == 2:
            self._set_provider(parts[1].strip().lower())
            return
        if parts and parts[0] == "key" and len(parts) == 2:
            cfg = load_ai_config()
            new_key = parts[1].strip()
            # vck_/sk-ant- switch the provider automatically; otherwise
            # the key belongs to the active provider (e.g. OpenAI's sk-...).
            provider = detect_provider(new_key) or active_provider(cfg)
            cfg["provider"] = provider
            set_config_key(cfg, provider, new_key)
            save_ai_config(cfg)
            self._client = None
            term.type_out(t("sysop.api_key_saved_for", provider=provider_label(provider)), delay=0.003)
            return
        if parts and parts[0] == "model" and len(parts) == 2:
            cfg = load_ai_config()
            cfg["model"] = parts[1].strip()
            save_ai_config(cfg)
            self._client = None
            term.type_out(t("sysop.model_set", model=parts[1].strip()), delay=0.003)
            return
        provider, key, base_url, model = self._resolve()
        term.rule(t("sysop.status_title"))
        if key:
            term.type_out(t("sysop.status_online", route=provider_label(provider)), delay=0.002)
            term.type_out(t("sysop.status_model", model=model), delay=0.002)
        else:
            term.type_out(t("sysop.status_offline"), delay=0.002)
        term.type_out(t("sysop.status_providers", providers=self._provider_overview()), delay=0.002)
        term.type_out(t("sysop.status_commands"), delay=0.002)
        term.rule()

    def _set_provider(self, name):
        """Switches the active provider (for 'ai provider <name>')."""
        term = self.term
        if name not in PROVIDERS:
            term.error(t("sysop.provider_unknown", name=name, list=", ".join(PROVIDERS)))
            return
        cfg = load_ai_config()
        cfg["provider"] = name
        save_ai_config(cfg)
        self._client = None
        term.type_out(t("sysop.provider_set", provider=provider_label(name)), delay=0.003)
        if not config_key(cfg, name) and not os.environ.get(ENV_KEYS[name]):
            term.type_out(t("sysop.provider_no_key", provider=provider_label(name)), delay=0.003)

    def _provider_overview(self):
        """Compact overview 'anthropic*, vercel, openai' — * marks the
        active one, [x] the ones with a stored key."""
        cfg = load_ai_config()
        current = active_provider(cfg)
        parts = []
        for provider in PROVIDERS:
            has = bool(config_key(cfg, provider) or os.environ.get(ENV_KEYS[provider]))
            token = provider + ("[x]" if has else "")
            parts.append("*" + token if provider == current else token)
        return "  ".join(parts)

    # -- Internal tools ---------------------------------------------------

    def _page_text(self, page):
        from .page import page_text
        header = f"Titel: {page.title}\nURL: {page.url}\n\n"
        return (header + page_text(page))[:MAX_PAGE_CHARS]

    def _page_snapshot(self, page):
        """Text plus links of a page — for tools that read in the background."""
        text = self._page_text(page)
        if page.links:
            listing = "\n".join(
                f"[{i}] {label} -> {url}"
                for i, (url, label) in enumerate(page.links[:40], 1)
            )
            text += f"\n\nLinks:\n{listing}"
        return text[:MAX_PAGE_CHARS]

    def _tool_registry(self):
        """Provider-neutral tool list: each entry has name, description, a
        JSON schema (parameters) and the Python function. Anthropic and OpenAI
        build their respective tool format from this (see _*_tool_defs)."""
        sysop = self
        browser = self.browser

        def _no_params():
            return {"type": "object", "properties": {}}

        def _one(name, typ, desc):
            return {"type": "object", "properties": {name: {"type": typ, "description": desc}},
                    "required": [name]}

        def seite_lesen():
            if not browser or not browser.page:
                return t("sysop.no_page_loaded")
            return sysop._page_text(browser.page)

        def links_auflisten():
            if not browser or not browser.page or not browser.page.links:
                return t("sysop.no_links_available")
            listing = "\n".join(
                f"[{i}] {label} -> {url}"
                for i, (url, label) in enumerate(browser.page.links, 1)
            )
            return listing[:MAX_PAGE_CHARS]

        def link_folgen(nummer):
            if not browser or not browser.page:
                return t("sysop.no_page_loaded")
            url = browser.page.link_url(int(nummer))
            if not url:
                return t("sysop.link_not_found", number=nummer, total=len(browser.page.links))
            browser.dial(url)
            return t("sysop.page_loaded", title=browser.page.title, url=browser.page.url)

        def seite_anwaehlen(url):
            if not browser:
                return t("sysop.error_browser_unavailable")
            browser.dial(url)
            if browser.page:
                return t("sysop.page_loaded", title=browser.page.title, url=browser.page.url)
            return t("sysop.error_dial_failed")

        def suchen(begriff):
            if not browser:
                return t("sysop.error_browser_unavailable")
            browser.search(begriff)
            if browser.page:
                return t("sysop.search_results_loaded")
            return t("sysop.search_failed")

        def im_netz_lesen(url):
            from .page import fetch_page, normalize_url
            fc_cfg = browser.firecrawl if browser else {}
            page, err = fetch_page(normalize_url(url), fc_cfg)
            if err:
                return t("sysop.error_no_carrier", error=err)
            snapshot = sysop._page_snapshot(page)
            # Firecrawl was on but failed (silent HTTP fallback): the
            # reason belongs in the tool result, otherwise the AI is left guessing.
            fc_error = getattr(page, "firecrawl_error", "")
            if fc_error:
                snapshot = t("sysop.firecrawl_note", error=fc_error) + "\n\n" + snapshot
            return snapshot

        def im_netz_suchen(begriff):
            from urllib.parse import quote_plus
            from .page import (
                fetch_page, firecrawl_search, normalize_base_url, page_text,
            )
            fc_cfg = browser.firecrawl if browser else {}
            fc_key = firecrawl_key(fc_cfg)
            fc_base = normalize_base_url(fc_cfg.get("base_url"))
            fc_err = None
            # Firecrawl configured? Then use the real search API — the
            # DDG HTML now mostly blocks automated requests.
            if fc_cfg.get("enabled") and (fc_key or fc_base):
                results, fc_err = firecrawl_search(begriff, fc_key, fc_base)
                if results:
                    listing = "\n".join(
                        f"[{i}] {title} -> {url}" + (f"\n    {desc}" if desc else "")
                        for i, (url, title, desc) in enumerate(results, 1)
                    )
                    return listing[:MAX_PAGE_CHARS]
            page, err = fetch_page(
                "https://html.duckduckgo.com/html/?q=" + quote_plus(begriff), fc_cfg
            )
            if page and page.links:
                listing = "\n".join(
                    f"[{i}] {label} -> {url}"
                    for i, (url, label) in enumerate(page.links, 1)
                )
                return listing[:MAX_PAGE_CHARS]
            # Nothing found: collect all reasons so the AI can tell
            # the caller WHY the search came back empty.
            reasons = [r for r in (
                fc_err, err, getattr(page, "firecrawl_error", "") if page else "",
            ) if r]
            if page:
                # DDG responded, but without result links — usually the
                # bot block; its message text explains the situation to the AI.
                excerpt = page_text(page)[:300].strip()
                if excerpt:
                    reasons.append(t("sysop.search_page_said", excerpt=excerpt))
            if reasons:
                return t("sysop.search_failed") + " " + " | ".join(reasons)
            return t("sysop.no_search_results")

        def funktionen_auflisten():
            from . import manual
            return "\n".join(
                f"{key} | {syntax} | {category} | {kurz}"
                for key, syntax, category, kurz, _ in manual.ALL
            )

        def funktion_erklaeren(name):
            from . import manual
            text = manual.explain(name)
            if text:
                return text
            keys = ", ".join(entry[0] for entry in manual.ALL)
            return f"Keine Funktion '{name}' im Handbuch. Bekannt sind: {keys}"  # internal error for the AI

        def chat_umbenennen(titel):
            titel = (titel or "").strip()[:CHAT_TITLE_MAX]
            db.chat_set_title(sysop.chat_channel, titel)
            if titel:
                return t("sysop.chat_renamed", title=titel)
            return t("sysop.chat_rename_cleared")

        def system_befehl(befehl):
            mode, timeout = shell_config()
            if mode == "off":
                return t("sysop.shell_disabled")
            befehl = (befehl or "").strip()
            if not befehl:
                return t("sysop.shell_empty")
            if mode == "confirm":
                # The caller sees the command in plain text and approves it —
                # without an explicit yes, nothing happens.
                sysop.term.type_out(t("sysop.shell_ask", command=befehl), delay=0.002)
                if not sysop.term.confirm(t("sysop.shell_confirm_prompt")):
                    return t("sysop.shell_denied")
            sysop.term.type_out(t("sysop.shell_running", command=befehl), delay=0.001)
            try:
                proc = subprocess.run(
                    befehl, shell=True, capture_output=True, text=True, timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                return t("sysop.shell_timeout", seconds=timeout)
            except Exception as e:
                return t("sysop.shell_error", error=str(e))
            output = "\n".join(part for part in (proc.stdout, proc.stderr) if part.strip())
            output = output.strip() or t("sysop.shell_no_output")
            return t("sysop.shell_result", code=proc.returncode,
                     output=output[:MAX_SHELL_OUTPUT])

        def firecrawl_scrape(url):
            fc_cfg = browser.firecrawl if browser else {}
            md = sysop.scrape_markdown(url, fc_cfg)
            return md[:MAX_PAGE_CHARS] if md else "Scrape fehlgeschlagen oder Firecrawl nicht konfiguriert."

        # -- App control: navigation, bookmarks, non-critical settings --

        def zurueck_blaettern():
            if not browser:
                return t("sysop.error_browser_unavailable")
            browser.back()
            if browser.page:
                return t("sysop.page_loaded", title=browser.page.title, url=browser.page.url)
            return t("sysop.no_page_loaded")

        def verlauf_anzeigen():
            from .nostalgia import recent_entries
            if not browser or not browser.history:
                return "Der Verlauf ist leer."
            return "\n".join(
                f"[{i}] {e.get('title') or ''} -> {e.get('url')}"
                for i, e in enumerate(recent_entries(browser.history, 20), 1))

        def lesezeichen_auflisten():
            if not browser or not browser.bookmarks:
                return "Keine Lesezeichen vorhanden."
            return "\n".join(
                f"[{i}] {b.get('title') or ''} -> {b.get('url')}"
                for i, b in enumerate(browser.bookmarks, 1))

        def lesezeichen_setzen():
            if not browser or not browser.page:
                return t("sysop.no_page_loaded")
            browser.add_bookmark()
            return f"Lesezeichen gesetzt: {browser.page.title} ({browser.page.url})"

        def lesezeichen_anwaehlen(nummer):
            if not browser:
                return t("sysop.error_browser_unavailable")
            browser.dial_bookmark(int(nummer))
            if browser.page:
                return t("sysop.page_loaded", title=browser.page.title, url=browser.page.url)
            return t("sysop.no_page_loaded")

        # Non-critical settings: everything from the display menu. API keys,
        # system access and MCP servers are deliberately left out — only the
        # caller can change those in the config menu.
        def _wahr(wert):
            return str(wert).strip().lower() in ("1", "an", "on", "true", "ja", "yes", "ein")

        def _settings_map():
            from . import i18n
            from .constants import (AMBER, GREEN, HEADER_MODES, IMG_SETTINGS,
                                    invalidate_layout)
            from .state import set_ui

            def farbe(wert):
                from . import colors

                mode = str(wert).strip().lower()
                if mode not in ("green", "amber", "auto", "multi"):
                    return "Erlaubt: green, amber, auto, multi."
                browser.color_auto = mode == "auto"
                colors.set_multi(mode == "multi")
                if mode == "multi":
                    sysop.term.color = colors.MULTI_TEXT
                elif mode != "auto":
                    sysop.term.color = GREEN if mode == "green" else AMBER
                set_ui("color", mode)
                return None

            def sprache(wert):
                lang = str(wert).strip().lower()
                if lang not in i18n.LANGUAGES:
                    return "Erlaubt: " + ", ".join(i18n.LANGUAGES) + "."
                i18n.set_lang(set_ui("lang", lang))
                return None

            def breite(wert):
                value = int(wert)
                set_ui("width", 0 if value <= 0 else max(80, value))
                invalidate_layout()
                return None

            def bilder(wert):
                mode = str(wert).strip().lower()
                mode = {"aus": "off", "an": "blocks", "bloecke": "blocks",
                        "halbbloecke": "blocks"}.get(mode, mode)
                if mode not in IMG_SETTINGS:
                    return "Erlaubt: blocks (Halbbloecke), ascii, aus."
                browser.images = set_ui("images", mode)
                return None

            def seitenkopf(wert):
                mode = str(wert).strip().lower()
                mode = {"aus": "off", "an": "logo"}.get(mode, mode)
                if mode not in HEADER_MODES:
                    return "Erlaubt: logo, banner, aus."
                browser.header = set_ui("header", mode)
                return None

            def _bool_setter(ui_key, apply):
                def setter(wert):
                    value = _wahr(wert)
                    set_ui(ui_key, apply(value) if apply else value)
                    return None
                return setter

            return {
                "bilder": ("blocks/ascii/aus — Bilder auf Seiten (blocks = Halbbloecke)", bilder),
                "bildbreite": ("Zahl — Breite gerenderter Bilder in Zeichen (min. 10)",
                               lambda w: setattr(browser, "img_width", set_ui("img_width", max(10, int(w)))) and None),
                "tipp_effekt": ("an/aus — Text zeichenweise austippen",
                                _bool_setter("fast", lambda v: _set_fast(not v))),
                "farbe": ("green/amber/auto/multi — Phosphorfarbe des Terminals"
                          " (multi = Rollenfarben im ANSI-BBS-Stil)", farbe),
                "baud": ("Zahl — simulierte Baudrate, 0 = aus",
                         lambda w: _set_baud(set_ui("baud", max(0, int(w))))),
                "sound": ("an/aus — Modemgeraeusche und Signaltoene",
                          _bool_setter("sound", lambda v: _set_sound(v))),
                "bildschirmschoner": ("Sekunden — Leerlauf bis zum Schoner, 0 = aus",
                                      lambda w: setattr(browser, "saver_idle", set_ui("saver_idle", max(0, int(w)))) and None),
                "sprache": ("de/en — Sprache der Oberflaeche", sprache),
                "breite": ("Zahl — Terminalbreite, 0 = Vollbild, sonst min. 80", breite),
                "seitenkopf": ("logo/banner/aus — Kopfzeile ueber Seiten", seitenkopf),
            }

        def _set_fast(value):
            sysop.term.fast = value
            return value

        def _set_baud(value):
            sysop.term.baud = value
            return None

        def _set_sound(value):
            sysop.term.sound = value
            return value

        def einstellungen_auflisten():
            if not browser:
                return t("sysop.error_browser_unavailable")
            return "\n".join(f"{name} — {desc}"
                             for name, (desc, _) in sorted(_settings_map().items()))

        def einstellung_aendern(name, wert):
            if not browser:
                return t("sysop.error_browser_unavailable")
            settings = _settings_map()
            entry = settings.get(str(name).strip().lower())
            if not entry:
                return ("Unbekannte Einstellung. Verfuegbar: "
                        + ", ".join(sorted(settings)))
            desc, setter = entry
            try:
                problem = setter(wert)
            except (TypeError, ValueError):
                return f"Ungueltiger Wert fuer '{name}' ({desc})."
            if problem:
                return problem
            return f"Einstellung '{name}' auf '{wert}' gesetzt."

        tools = [
            {"name": "seite_lesen", "func": seite_lesen, "parameters": _no_params(),
             "description": "Liest die aktuell im Browser geladene Seite (Titel, URL und kompletter Text)."},
            {"name": "links_auflisten", "func": links_auflisten, "parameters": _no_params(),
             "description": "Listet alle nummerierten Links der aktuell geladenen Seite mit Nummer, Beschriftung und Ziel-URL."},
            {"name": "link_folgen", "func": link_folgen,
             "parameters": _one("nummer", "integer", "Die Link-Nummer aus links_auflisten (1-basiert)."),
             "description": "Folgt dem Link mit der angegebenen Nummer auf der aktuellen Seite und laedt die Zielseite in den Browser."},
            {"name": "seite_anwaehlen", "func": seite_anwaehlen,
             "parameters": _one("url", "string", "Die anzuwaehlende Adresse."),
             "description": "Waehlt eine URL an und laedt sie in den Browser des Anrufers."},
            {"name": "suchen", "func": suchen,
             "parameters": _one("begriff", "string", "Der Suchbegriff."),
             "description": "Sucht via DuckDuckGo und laedt die Ergebnisseite in den Browser."},
            {"name": "im_netz_lesen", "func": im_netz_lesen,
             "parameters": _one("url", "string", "Die zu lesende Adresse."),
             "description": "Laedt eine URL im Hintergrund und liefert Titel, Text und Links zurueck, OHNE den Bildschirm des Anrufers zu veraendern. Nutze das zum eigenstaendigen Surfen und Recherchieren; seite_anwaehlen nur, wenn der Anrufer die Seite selbst sehen soll."},
            {"name": "im_netz_suchen", "func": im_netz_suchen,
             "parameters": _one("begriff", "string", "Der Suchbegriff."),
             "description": "Sucht via DuckDuckGo im Hintergrund und liefert die Treffer mit URLs zurueck, OHNE den Bildschirm des Anrufers zu veraendern. Ergebnisse danach bei Bedarf mit im_netz_lesen vertiefen."},
            {"name": "funktionen_auflisten", "func": funktionen_auflisten, "parameters": _no_params(),
             "description": "Listet alle Funktionen und Befehle des BBS-Browsers mit Befehl, Syntax, Kategorie und Kurzbeschreibung. Nutze das, wenn der Anrufer wissen will, was der Browser kann."},
            {"name": "funktion_erklaeren", "func": funktion_erklaeren,
             "parameters": _one("name", "string", "Befehl oder Stichwort, z.B. 'rss', 'l', 'chat', 'baud', 'firecrawl'."),
             "description": "Erklaert eine einzelne Funktion des BBS-Browsers ausfuehrlich. Nutze das immer, wenn der Anrufer fragt, wie etwas funktioniert oder was ein Befehl macht — antworte nie aus dem Gedaechtnis."},
            {"name": "chat_umbenennen", "func": chat_umbenennen,
             "parameters": _one("titel", "string", "Kurzer Name fuer diesen Chat, max. 40 Zeichen. Leer laesst den Standardnamen zurueckkehren."),
             "description": "Benennt den laufenden Chat um; der Name erscheint im Verlauf ('log'). Nutze das, wenn der Anrufer einen Namen wuenscht oder das Thema des Chats klar geworden ist."},
            {"name": "firecrawl_scrape", "func": firecrawl_scrape,
             "parameters": _one("url", "string", "Die zu scrapende Adresse."),
             "description": "Scraped eine JS-lastige Seite ueber Firecrawl und liefert das Markdown. Nur nutzen, wenn die normale Anwahl zu wenig Inhalt liefert."},
            {"name": "zurueck_blaettern", "func": zurueck_blaettern, "parameters": _no_params(),
             "description": "Blaettert im Browser des Anrufers eine Seite zurueck (wie der Befehl 'b')."},
            {"name": "verlauf_anzeigen", "func": verlauf_anzeigen, "parameters": _no_params(),
             "description": "Listet die letzten 20 besuchten Seiten mit Nummer, Titel und URL."},
            {"name": "lesezeichen_auflisten", "func": lesezeichen_auflisten, "parameters": _no_params(),
             "description": "Listet alle Lesezeichen des Anrufers mit Nummer, Titel und URL."},
            {"name": "lesezeichen_setzen", "func": lesezeichen_setzen, "parameters": _no_params(),
             "description": "Setzt ein Lesezeichen auf die aktuell geladene Seite."},
            {"name": "lesezeichen_anwaehlen", "func": lesezeichen_anwaehlen,
             "parameters": _one("nummer", "integer", "Die Nummer aus lesezeichen_auflisten (1-basiert)."),
             "description": "Waehlt ein Lesezeichen an und laedt es in den Browser des Anrufers."},
            {"name": "einstellungen_auflisten", "func": einstellungen_auflisten, "parameters": _no_params(),
             "description": "Listet alle Einstellungen, die du fuer den Anrufer aendern darfst, mit erlaubten Werten. Immer zuerst aufrufen, bevor du eine Einstellung aenderst."},
            {"name": "einstellung_aendern", "func": einstellung_aendern,
             "parameters": {"type": "object", "properties": {
                 "name": {"type": "string", "description": "Name der Einstellung aus einstellungen_auflisten."},
                 "wert": {"type": "string", "description": "Der neue Wert, z.B. 'an', 'aus', 'green', '9600', 'de'."},
             }, "required": ["name", "wert"]},
             "description": "Aendert eine unkritische Einstellung (Anzeige, Sound, Sprache, Baud usw.) fuer den Anrufer. API-Keys, Systemzugriff und MCP-Server kannst du NICHT aendern — dafuer den Anrufer ins Config-Menue ('c') schicken."},
        ]
        # Tools of the registered MCP servers: our own MCP client makes
        # them available to every provider, not just direct Anthropic.
        try:
            from . import mcp
            tools.extend(mcp.registry_tools())
        except Exception:
            pass    # a broken MCP server must not block the chat
        # System access is only offered to the model if the caller has
        # enabled it — otherwise the agent doesn't even know the tool exists.
        if shell_enabled():
            tools.append({
                "name": "system_befehl", "func": system_befehl,
                "parameters": _one("befehl", "string",
                                   "Der auszufuehrende Shell-Befehl, z.B. 'uname -a' oder 'ls ~'."),
                "description": (
                    "Fuehrt einen Shell-Befehl auf dem Rechner des Anrufers aus und liefert "
                    "Exit-Code und Ausgabe zurueck. Nutze das nur, wenn der Anrufer wirklich "
                    "etwas am System wissen oder tun will. Sei sparsam und vorsichtig: keine "
                    "zerstoerenden Befehle (rm -rf, Formatieren, Herunterfahren) ohne "
                    "ausdruecklichen Auftrag, und keine interaktiven Programme, die auf "
                    "Eingaben warten."
                ),
            })
        return tools

    # -- Agent run ------------------------------------------------------

    def run(self, instruction, history=None, max_tokens=1500, quiet=False):
        """A request to the SysOp agent. Returns the final text.

        Both providers go through the same tool registry; only the
        message/tool format differs (Anthropic vs. OpenAI)."""
        client = self.client()
        if not client:
            return None
        term = self.term
        messages = list(history or []) + [{"role": "user", "content": instruction}]
        # In chat, a rule line per reply is distracting; a short label
        # before the first line is enough there.
        if quiet:
            self._reply_prefix = t("sysop.chat_reply_prefix")
        else:
            self._reply_prefix = None
            term.rule(t("sysop.agent_title"))
        try:
            if self._provider == "openai":
                final = self._run_openai(client, messages, max_tokens)
            else:
                final = self._run_anthropic(client, messages, max_tokens)
        except Exception as e:
            term.error(t("sysop.error_agent", error=str(e)))
            return None
        self._status_done()
        if not quiet:
            term.rule()
        return final

    def _status(self, text):
        """Progress on the transient status line — only the latest step
        shows. Dummy terminals without status() get a plain line."""
        status = getattr(self.term, "status", None)
        if status:
            status(text)
        else:
            self.term.type_out(text, delay=0.001)

    def _status_done(self):
        clear = getattr(self.term, "status_clear", None)
        if clear:
            clear()

    def _dispatch(self, registry, name, args):
        """Calls a tool; catches errors and always returns a string."""
        func = next((tool["func"] for tool in registry if tool["name"] == name), None)
        if func is None:
            return f"Unbekanntes Werkzeug: {name}"
        try:
            return str(func(**(args or {})))
        except Exception as e:
            return f"Fehler im Werkzeug {name}: {e}"

    def _emit_text(self, text):
        """Emits an AI text block and returns it (trimmed).

        The AI replies in Markdown; rich renders it in the phosphor tone. Emoji
        is filtered by markdown.render for ALL chat paths — here again before
        output, so the stored history also stays clean."""
        from .markdown import strip_emoji

        text = strip_emoji((text or "").strip())
        if text:
            self._status_done()  # reply text ends the tool status line
            prefix, self._reply_prefix = self._reply_prefix, None
            self.term.markdown(text, prefix=prefix, image=self._image_art)
        return text

    def _image_art(self, url, alt=""):
        """Typesets an image out of a chat reply the same way a page does —
        half-blocks or ASCII per the display setting, 'off' leaves the label.
        """
        from .constants import screen_lines
        from .images import fetch_image

        browser = self.browser
        if browser is None or not browser.render_images:
            return None
        return fetch_image(url, width=browser.img_width, mode=browser.img_mode,
                           max_lines=max(1, screen_lines() - 2))

    def _run_anthropic(self, client, messages, max_tokens,
                       system=None, registry=None, steps=MAX_AGENT_STEPS, emit=True):
        from .markdown import strip_emoji

        registry = self._tool_registry() if registry is None else registry
        tools = _anthropic_tool_defs(registry)
        convo = list(messages)
        final_text = []
        for _ in range(steps):
            resp = self._anthropic_round(client, convo, tools, max_tokens, system, emit)
            self.track(resp)
            convo.append({"role": "assistant",
                          "content": _plain_blocks(resp.content)})
            tool_uses = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
            for block in resp.content:
                if getattr(block, "type", None) != "text":
                    continue
                # In streaming mode the text is already on screen — here it
                # is only collected (emoji-free, like the emitted version).
                text = strip_emoji((block.text or "").strip()) if emit \
                    else (block.text or "").strip()
                if text:
                    final_text.append(text)
            if not tool_uses:
                break
            results = []
            for block in tool_uses:
                self._status(t("sysop.agent_tool_use", name=tool_label(block.name)))
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": self._dispatch(registry, block.name, block.input)})
            convo.append({"role": "user", "content": results})
        return "\n".join(final_text) or None

    def _anthropic_round(self, client, convo, tools, max_tokens, system, live):
        """One model round. `live` streams: text appears paragraph by
        paragraph, tool calls show up on the status line the moment the
        model starts them."""
        kwargs = dict(model=self._model, max_tokens=max_tokens,
                      system=system or persona(), tools=tools, messages=convo)
        if not live or not hasattr(client.messages, "stream"):
            resp = client.messages.create(**kwargs)
            if live:    # client without streaming (e.g. test doubles)
                for block in resp.content:
                    if getattr(block, "type", None) == "text":
                        self._emit_text(block.text)
            return resp
        out = _ParagraphStream(self._emit_text)
        with client.messages.stream(**kwargs) as stream:
            for event in stream:
                etype = getattr(event, "type", "")
                if etype == "text":
                    out.feed(event.text)
                elif (etype == "content_block_start"
                      and getattr(event.content_block, "type", "") == "tool_use"):
                    self._status(t("sysop.agent_tool_use",
                                   name=tool_label(event.content_block.name)))
            resp = stream.get_final_message()
        out.close()
        return resp

    def _run_openai(self, client, messages, max_tokens,
                    system=None, registry=None, steps=MAX_AGENT_STEPS, emit=True):
        from .markdown import strip_emoji

        registry = self._tool_registry() if registry is None else registry
        tools = _openai_tool_defs(registry)
        convo = [{"role": "system", "content": system or persona()}] + list(messages)
        final_text = []
        for _ in range(steps):
            raw, calls, usage = self._openai_round(client, convo, tools, max_tokens, emit)
            self.track(usage)
            text = strip_emoji(raw.strip()) if emit else raw.strip()
            if text:
                final_text.append(text)
            if not calls:
                break
            convo.append({"role": "assistant", "content": raw or "", "tool_calls": [
                {"id": tc["id"], "type": "function",
                 "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                for tc in calls
            ]})
            for tc in calls:
                self._status(t("sysop.agent_tool_use", name=tool_label(tc["name"])))
                try:
                    args = json.loads(tc["arguments"] or "{}")
                except (ValueError, TypeError):
                    args = {}
                convo.append({"role": "tool", "tool_call_id": tc["id"],
                              "content": self._dispatch(registry, tc["name"], args)})
        return "\n".join(final_text) or None

    def _openai_round(self, client, convo, tools, max_tokens, live):
        """One model round. Returns (text, tool calls as dicts, usage
        carrier). `live` streams: text appears paragraph by paragraph,
        tool calls hit the status line as soon as their name arrives."""
        kwargs = dict(model=self._model, max_tokens=max_tokens,
                      messages=convo, tools=tools)
        if live:
            stream = self._open_openai_stream(client, kwargs)
            if stream is not None:
                return self._consume_openai_stream(stream)
        resp = client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        if live:
            self._emit_text(msg.content)
        calls = [{"id": tc.id, "name": tc.function.name,
                  "arguments": tc.function.arguments or ""}
                 for tc in (msg.tool_calls or [])]
        return msg.content or "", calls, _openai_usage(resp)

    def _open_openai_stream(self, client, kwargs):
        """Opens a completion stream; None when the gateway (or a test
        double) doesn't support streaming — the round then runs one-shot."""
        try:
            return client.chat.completions.create(
                stream=True, stream_options={"include_usage": True}, **kwargs)
        except Exception:
            pass    # maybe just stream_options unknown — once more without
        try:
            return client.chat.completions.create(stream=True, **kwargs)
        except Exception:
            return None

    def _consume_openai_stream(self, stream):
        out = _ParagraphStream(self._emit_text)
        parts, slots, usage = [], {}, None
        for chunk in stream:
            usage = getattr(chunk, "usage", None) or usage
            if not getattr(chunk, "choices", None):
                continue
            delta = chunk.choices[0].delta
            if delta is None:
                continue
            if delta.content:
                parts.append(delta.content)
                out.feed(delta.content)
            for tc in (delta.tool_calls or []):
                slot = slots.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                if tc.id:
                    slot["id"] = tc.id
                fn = tc.function
                if fn and fn.name and not slot["name"]:
                    slot["name"] = fn.name
                    self._status(t("sysop.agent_tool_use", name=tool_label(fn.name)))
                if fn and fn.arguments:
                    slot["arguments"] += fn.arguments
        out.close()
        calls = [slots[i] for i in sorted(slots) if slots[i]["name"]]
        if usage is not None:
            usage = _UsageCarrier(_NormalizedUsage(
                getattr(usage, "prompt_tokens", 0),
                getattr(usage, "completion_tokens", 0)))
        else:
            usage = _UsageCarrier(None)
        return "".join(parts), calls, usage

    def _raw_complete(self, system, messages, max_tokens):
        """A single completion without tools, provider-neutral. Returns the
        plain text (possibly '') or None (offline). Raises on API errors; counts
        usage."""
        client = self.client()
        if not client:
            return None
        if self._provider == "openai":
            convo = [{"role": "system", "content": system}] + list(messages)
            resp = client.chat.completions.create(
                model=self._model, max_tokens=max_tokens, messages=convo,
            )
            self.track(_openai_usage(resp))
            return resp.choices[0].message.content or ""
        resp = client.messages.create(
            model=self._model, max_tokens=max_tokens, system=system, messages=list(messages),
        )
        self.track(resp)
        return "".join(b.text for b in resp.content if b.type == "text")

    def converse(self, system, messages, max_tokens=600):
        """Lightweight AI call without tools — for conversations that need no
        tool (e.g. the AI caller). Returns the text or None."""
        if not self.client():
            return None
        try:
            text = self._raw_complete(system, messages, max_tokens)
        except Exception as e:
            self.term.error(t("sysop.error_agent", error=str(e)))
            return None
        return (text or "").strip() or None

    # -- Style templates: learn once per domain, apply locally ------------

    @property
    def TEMPLATE_SYSTEM(self):
        return t("sysop.templater")

    def build_template(self, page):
        """The `x` path: learns ONE style template for the page's domain and
        returns it, or None. The AI takes the site apart with tools
        (outline/probe/preview) and corrects its draft until it holds up on
        the verification pages too. Costs a handful of calls — once per
        domain; every further page of that domain then stays free.

        What counts is what preview() MEASURED, not what the AI claims at
        the end."""
        from . import styletpl

        client = self.client()
        if not client or not styletpl.eligible(page):
            return None
        term = self.term
        term.type_out(t("sysop.learning_template"), delay=0.005)

        try:
            samples = styletpl.collect_samples(
                page, self._plain_page,
                log=lambda url: self._status(
                    t("sysop.template_verify_page", url=url)),
                # Same line the browser dials with — Firecrawl included, if
                # it is configured. Otherwise the verification pages would
                # arrive thinner than the page the template has to fit.
                firecrawl_cfg=getattr(self.browser, "firecrawl", None),
            )
            box = styletpl.Toolbox(samples, self._build_with)
            plan = box.outline()
        except Exception as e:
            term.error(t("sysop.error_template", error=str(e)))
            return None
        if plan == "(empty)":
            return None

        registry = self._templater_registry(box)
        prompt = (
            f"Domain: {styletpl.domain_of(page.url)}\n"
            f"Verification pages:\n"
            + "\n".join(f"  [{i + 1}] {s.url}" for i, s in enumerate(samples))
            + f"\n\nOutline of page 1:\n{plan}"
            + self._template_revision(box, page)
        )
        try:
            runner = (
                self._run_openai if self._provider == "openai" else self._run_anthropic
            )
            answer = runner(
                client, [{"role": "user", "content": prompt}], 2000,
                system=self.TEMPLATE_SYSTEM, registry=registry,
                steps=MAX_TEMPLATE_STEPS, emit=False,
            )
        except Exception as e:
            term.error(t("sysop.error_template", error=str(e)))
            return (box.best, box.verified, len(samples)) if box.best else None
        self._status_done()

        # A measurably passing draft beats the closing text; only if the AI
        # never called preview() is its answer evaluated at all.
        if box.best:
            return box.best, box.verified, len(samples)
        clean = styletpl.sanitize(answer or "", box.soup)
        return (clean, 0, len(samples)) if clean else None

    def _template_revision(self, box, page):
        """'x' on a domain that already has a template is a REVISION, not a
        fresh start: the existing template goes through the proof run first,
        so its score becomes the mark to beat, and both it and its result go
        into the prompt. Whatever still fits the site stays; only what the
        proof run shows to be broken gets changed. Empty string when there
        is nothing stored yet."""
        import json

        from . import styletpl

        stored = styletpl.load(page.url)
        if not stored:
            return ""
        old = dict(stored)
        # Seeding the toolbox means a new draft only wins when it MEASURES
        # better — a revision can never come out worse than what we had.
        report = box.preview(old)
        self._status(t("sysop.template_revising"))
        return (
            "\n\nThis domain ALREADY has a template. Your job is to UPDATE it, "
            "not to invent a new one: keep every selector that still holds and "
            "change only what the proof run below shows to be broken (site "
            "redesign, renamed classes, new banners). Fewer, targeted edits "
            "are better than a rewrite.\n"
            f"Current template:\n{json.dumps(old, ensure_ascii=False)}\n"
            f"Proof run of the current template:\n{report}"
        )

    def _plain_page(self, html, url):
        """Baseline build without a template — the yardstick preview()
        measures a draft against."""
        return self._build_with(html, url, None)

    def _build_with(self, html, url, template):
        """Builds a page from raw HTML, optionally with a template. Images
        stay off: the verification measures text, and re-fetching pictures
        for every draft would make learning unbearably slow."""
        from .page import build_page

        try:
            return build_page(html, url, render_images=False, template=template)
        except Exception:
            return None

    def _templater_registry(self, box):
        """The learning loop's tools in the agent format (see
        _tool_registry) — named like the trade they imitate: a type spec, a
        blueprint, a proof run. Deliberately only these three: the setter is
        meant to examine the site, not remote-control the browser."""
        def _sel(required, desc):
            schema = {"type": "object",
                      "properties": {"selektor": {"type": "string", "description": desc}}}
            if required:
                schema["required"] = ["selektor"]
            return schema

        return [
            {
                "name": "satzprobe",
                "description": (
                    "Satzprobe zu einem CSS-Selektor: Trefferzahl auf JEDER "
                    "Fahne, dazu Tag, Zeichenzahl und Textprobe auf Fahne 1. "
                    "Damit erkennst du, ob ein Selektor eine Ueberschrift "
                    "greift oder einen ganzen Inhaltsblock. Ein Selektor, der "
                    "nur auf Fahne 1 trifft, taugt nicht fuer die Domain."
                ),
                "parameters": _sel(True, "Der zu pruefende CSS-Selektor."),
                "func": lambda selektor: box.probe(selektor),
            },
            {
                "name": "bauplan",
                "description": (
                    "Bauplan eines Teilbaums: Tags mit Klassen/IDs und die "
                    "Zeichenzahl darunter, ohne den Text. Ohne Selektor die "
                    "ganze Fahne 1. Nutze das, um dich in einen Bereich "
                    "hineinzugraben."
                ),
                "parameters": _sel(False, "Optionaler CSS-Selektor der Wurzel."),
                "func": lambda selektor="": box.outline(selektor),
            },
            {
                "name": "andruck",
                "description": (
                    "Andruck deines Entwurfs auf ALLEN Fahnen: meldet je Fahne "
                    "die Zeichenbilanz gegen den Handsatz, jede abgelehnte "
                    "Regel und den Blocksatz von Fahne 1. Rufe das auf, BEVOR "
                    "du fertig bist, und korrigiere, was danebengreift."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"vorlage": {
                        "type": "string",
                        "description": "Der Entwurf als JSON-Objekt (content/drop/rules/note).",
                    }},
                    "required": ["vorlage"],
                },
                "func": lambda vorlage: box.preview(vorlage),
            },
        ]

    # -- Commands ---------------------------------------------------------

    def summarize(self, page):
        if not page:
            self.term.error(t("sysop.error_no_page_for_action"))
            return
        self.run(
            "Lies die aktuelle Seite mit seite_lesen und fasse sie als "
            "SysOp-Digest fuer eilige Anrufer zusammen, maximal 8 Zeilen."
        )

    def ask(self, page, question):
        if not page:
            self.term.error(t("sysop.error_no_page_for_action"))
            return
        self.run(
            f"Beantworte mit Hilfe von seite_lesen diese Frage zur aktuellen "
            f"Seite: {question}\nWenn die Seite es nicht hergibt, sag das ehrlich."
        )

    def navigate(self, description):
        """'go <description>': agent looks for the matching link and follows it."""
        self.run(
            f"Der Anrufer moechte dorthin: \"{description}\". Sieh dir mit "
            "links_auflisten die Links der aktuellen Seite an, waehle den am "
            "besten passenden und folge ihm mit link_folgen. Wenn keiner passt, "
            "sag es kurz und folge keinem Link."
        )

    # -- Chat (several conversations side by side) -------------------------

    def chat_label(self, channel=None):
        """Display name of a chat: its title, else 'SYSOP' / 'SYSOP #N'."""
        channel = channel or self.chat_channel
        title = db.chat_title(channel)
        if title:
            return title
        if channel == CHAT_CHANNEL:
            return t("chatlog.channel_sysop")
        return t("chatlog.channel_sysop_n", num=channel.rsplit(":", 1)[-1])

    def _switch_chat(self, channel):
        """Makes `channel` the active conversation and loads its history."""
        self.chat_channel = channel
        self.chat_history = db.chat_history(channel, limit=20)
        self._chat_ctx_url = None
        db.set_active_chat(channel)

    def new_chat(self):
        """Opens a fresh conversation. The base channel is reused as long
        as it has never been written to."""
        if not db.chat_history(CHAT_CHANNEL, limit=1) and not db.chat_title(CHAT_CHANNEL):
            self._switch_chat(CHAT_CHANNEL)
        else:
            self._switch_chat(db.new_chat_channel(CHAT_CHANNEL))
        return self.chat_channel

    def chat_board(self):
        """The 'chat' command: pick a conversation from the board, then talk.
        With no stored chats it jumps straight into the first one."""
        if db.chat_channels(prefix=CHAT_CHANNEL):
            picked = self._pick_chat()
            if not picked:
                return
            if picked == "new":
                self.new_chat()
            else:
                self._switch_chat(picked)
        self.chat()

    def _pick_chat(self):
        """Lightbar board of all SysOp chats. Returns a channel, 'new',
        or None for back. 'x' deletes the highlighted conversation."""
        from . import lightbar
        term = self.term

        def entries():
            return db.chat_channels(prefix=CHAT_CHANNEL)

        def rows():
            out = []
            for i, e in enumerate(entries(), 1):
                marker = "» " if e["channel"] == self.chat_channel else "  "
                label = (marker + self.chat_label(e["channel"]))[:34]
                out.append((str(i), label, t(
                    "sysop.board_line", count=e["count"],
                    when=_chat_when(e["last"]))))
            out.append((None, "", ""))
            out.append(("n", t("sysop.board_new"), ""))
            return out

        def on_key(pressed, key):
            if pressed not in ("x", "X") or not key or not key.isdigit():
                return False
            listing = entries()
            idx = int(key) - 1
            if not 0 <= idx < len(listing):
                return False
            channel = listing[idx]["channel"]
            db.chat_clear(channel)
            if channel == self.chat_channel:
                self._switch_chat(CHAT_CHANNEL)
            return True

        choice = lightbar.menu(
            term, t("sysop.board_title"), rows,
            on_key=on_key, hint=t("sysop.board_hint"), page_size=14,
        )
        if choice == lightbar.BACK:
            return None
        if choice == "n":
            return "new"
        listing = entries()
        if choice.isdigit() and 1 <= int(choice) <= len(listing):
            return listing[int(choice) - 1]["channel"]
        return None

    def _chat_divider(self):
        """Dotted line between chat exchanges — keeps the transcript scannable."""
        from .constants import DIM, RESET, screen_width
        self.term.type_out(DIM + "┄" * screen_width() + RESET, delay=0)

    def _replay_tail(self):
        """A few lines of the stored conversation, dimmed — so resuming a
        chat feels like picking up the thread, not starting over."""
        from .constants import DIM, RESET
        lines = db.chat_transcript(self.chat_channel, limit=REPLAY_LINES)
        if not lines:
            return
        you, name = t("sysop.chat_prompt").strip(), t("sysop.chat_reply_prefix").strip()
        for line in lines:
            who = you if line["role"] == "user" else name
            text = " ".join((line["text"] or "").split())[:200]
            self.term.type_out(DIM + f"{who} {text}" + RESET, delay=0.0005)
        self._chat_divider()

    def _auto_title(self, question, reply):
        """Names an untitled chat after the first exchange — one cheap
        completion; failures stay silent."""
        try:
            text = self._raw_complete(
                t("sysop.title_system"),
                [{"role": "user",
                  "content": f"{question}\n---\n{(reply or '')[:600]}"}],
                30,
            )
        except Exception:
            return
        lines = (text or "").strip().strip('"\'').splitlines()
        title = lines[0][:CHAT_TITLE_MAX].strip() if lines else ""
        if title:
            db.chat_set_title(self.chat_channel, title)
            self.term.type_out(t("sysop.chat_titled", title=title), delay=0.002)

    def _chat_command(self, msg):
        """Slash commands inside the chat. Returns 'handled', 'board', or None."""
        low = msg.lower()
        if low in ("/neu", "/new"):
            self.new_chat()
            self.term.type_out(t("sysop.chat_new_started"), delay=0.003)
            return "handled"
        if low in ("/chats", "/menu", "/board"):
            return "board"
        if low.startswith("/name"):
            title = msg[5:].strip()[:CHAT_TITLE_MAX]
            db.chat_set_title(self.chat_channel, title)
            self.term.type_out(
                t("sysop.chat_renamed", title=title) if title
                else t("sysop.chat_rename_cleared"), delay=0.003)
            return "handled"
        if low.startswith("/"):
            self.term.type_out(t("sysop.chat_commands"), delay=0.003)
            return "handled"
        return None

    def chat(self, channel=None):
        """Interactive chat with the SysOp. Empty input or 'exit' ends it;
        /neu, /chats and /name manage the conversations."""
        if channel and channel != self.chat_channel:
            self._switch_chat(channel)
        while True:
            result = self._chat_session()
            if result != "board":
                return
            picked = self._pick_chat()
            if not picked:
                return
            if picked == "new":
                self.new_chat()
            else:
                self._switch_chat(picked)

    def _chat_session(self):
        """One stretch of conversation in the active channel. Returns
        'board' when the caller asked for the chat board, else None."""
        term = self.term
        if not self.client():
            return None
        from .constants import DIM, RESET
        term.rule(t("sysop.chat_title_named", name=self.chat_label()))
        self._replay_tail()
        term.type_out(t("sysop.chat_connected"), delay=0.003)
        term.type_out(DIM + t("sysop.chat_commands") + RESET, delay=0.0005)
        while True:
            msg = term.prompt(t("sysop.chat_prompt"))
            if not msg or msg.lower() in ("exit", "quit", "q"):
                term.type_out(t("sysop.chat_goodbye"), delay=0.003)
                term.rule()
                return None
            handled = self._chat_command(msg)
            if handled == "board":
                term.rule()
                return "board"
            if handled == "handled":
                # A command may have switched the channel — reprint the header.
                term.rule(t("sysop.chat_title_named", name=self.chat_label()))
                continue
            # Provide the current page as context once (and again as
            # soon as the caller has a different page on screen).
            instruction = msg
            page = self.browser.page if self.browser else None
            if page and page.url != self._chat_ctx_url:
                self._chat_ctx_url = page.url
                ctx = self._page_text(page)[:6000]
                instruction = (
                    f"[Kontext — diese Seite hat der Anrufer gerade auf dem Schirm:]\n"
                    f"{ctx}\n[Ende Kontext]\n\nAnrufer: {msg}"
                )
            reply = self.run(
                instruction, history=self.chat_history[-20:], max_tokens=800, quiet=True,
            )
            if reply is None:
                # Empty reply (e.g. only tool rounds with no final text) doesn't
                # end the whole session — wait for the next question.
                term.error(t("sysop.chat_no_reply"))
                continue
            # Save with context, so the page stays known for follow-up questions;
            # for review ('log') `display` holds just the plain question.
            self.chat_history.append({"role": "user", "content": instruction})
            self.chat_history.append({"role": "assistant", "content": reply})
            db.chat_append(self.chat_channel, "user", instruction, display=msg)
            db.chat_append(self.chat_channel, "assistant", reply)
            # First full exchange in an untitled chat: let the AI name it,
            # the way every modern chat client does — but only once.
            if self.chat_channel not in self._titled and not db.chat_title(self.chat_channel):
                self._titled.add(self.chat_channel)
                self._auto_title(msg, reply)
            self._chat_divider()

    # -- Firecrawl via MCP ----------------------------------------------

    def scrape_markdown(self, url, fc_cfg):
        """Scrapes a page via the Firecrawl MCP server (Claude MCP connector).
        Returns markdown or None. Needs a direct Anthropic key — the MCP
        connector runs neither through the Vercel gateway nor through OpenAI."""
        client = self.client()
        if not client:
            return None
        if self._provider != "anthropic":
            self.term.error(t("sysop.error_firecrawl_needs_anthropic"))
            return None
        fc_key = firecrawl_key(fc_cfg)
        mcp_url = fc_cfg.get("base_url") or (
            f"https://mcp.firecrawl.dev/{fc_key}/v2/mcp" if fc_key else None
        )
        if not mcp_url:
            self.term.error(t("sysop.error_firecrawl_not_configured"))
            return None
        self.term.type_out(t("sysop.scraping"), delay=0.005)
        try:
            resp = client.beta.messages.create(
                model=self._model,
                max_tokens=8000,
                betas=["mcp-client-2025-11-20"],
                mcp_servers=[{"type": "url", "url": mcp_url, "name": "firecrawl"}],
                tools=[{"type": "mcp_toolset", "mcp_server_name": "firecrawl"}],
                system=(
                    "Du bedienst das Firecrawl-Scrape-Tool. Scrape die angefragte "
                    "Seite und gib ausschliesslich das Markdown der Seite zurueck, "
                    "ohne eigene Kommentare."
                ),
                messages=[{"role": "user", "content": f"Scrape {url} und gib nur das Markdown zurueck."}],
            )
        except Exception as e:
            self.term.error(t("sysop.error_firecrawl", error=str(e)))
            return None
        self.track(resp)
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        return text or None
