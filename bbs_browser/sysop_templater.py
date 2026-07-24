"""Style-template learning: the SysOp's `x` path.

Learns ONE style template per domain with an agentic tool loop
(outline/probe/preview) and verifies drafts against sample pages. The
functions here take the SysOp instance as their first parameter — sysop.py
keeps thin delegating methods, so callers stay unchanged and no import
cycle arises (this module never imports sysop at module level).
"""

from .i18n import t
from .sysop_config import MAX_TEMPLATE_STEPS
from .sysop_tools import build_templater_registry


def template_system():
    return t("sysop.templater")


def build_template(sysop, page):
    """The `x` path: learns ONE style template for the page's domain and
    returns it, or None. The AI takes the site apart with tools
    (outline/probe/preview) and corrects its draft until it holds up on
    the verification pages too. Costs a handful of calls — once per
    domain; every further page of that domain then stays free.

    What counts is what preview() MEASURED, not what the AI claims at
    the end."""
    from . import styletpl

    client = sysop.client()
    if not client or not styletpl.eligible(page):
        return None
    term = sysop.term
    term.type_out(t("sysop.learning_template"), delay=0.005)

    try:
        samples = styletpl.collect_samples(
            page, sysop._plain_page,
            log=lambda url: sysop._status(
                t("sysop.template_verify_page", url=url)),
            # Same line the browser dials with — Firecrawl included, if
            # it is configured. Otherwise the verification pages would
            # arrive thinner than the page the template has to fit.
            firecrawl_cfg=getattr(sysop.browser, "firecrawl", None),
        )
        box = styletpl.Toolbox(samples, sysop._build_with)
        plan = box.outline()
    except Exception as e:
        term.error(t("sysop.error_template", error=str(e)))
        return None
    if plan == "(empty)":
        return None

    registry = sysop._templater_registry(box)
    prompt = (
        f"Domain: {styletpl.domain_of(page.url)}\n"
        f"Verification pages:\n"
        + "\n".join(f"  [{i + 1}] {s.url}" for i, s in enumerate(samples))
        + f"\n\nOutline of page 1:\n{plan}"
        + sysop._template_revision(box, page)
    )
    try:
        runner = (
            sysop._run_openai if sysop._provider == "openai" else sysop._run_anthropic
        )
        answer = runner(
            client, [{"role": "user", "content": prompt}], 2000,
            system=sysop.TEMPLATE_SYSTEM, registry=registry,
            steps=MAX_TEMPLATE_STEPS, emit=False,
        )
    except Exception as e:
        term.error(t("sysop.error_template", error=str(e)))
        return (box.best, box.verified, len(samples)) if box.best else None
    sysop._status_done()

    # A measurably passing draft beats the closing text; only if the AI
    # never called preview() is its answer evaluated at all.
    if box.best:
        return box.best, box.verified, len(samples)
    clean = styletpl.sanitize(answer or "", box.soup)
    return (clean, 0, len(samples)) if clean else None


def template_revision(sysop, box, page):
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
    sysop._status(t("sysop.template_revising"))
    return (
        "\n\nThis domain ALREADY has a template. Your job is to UPDATE it, "
        "not to invent a new one: keep every selector that still holds and "
        "change only what the proof run below shows to be broken (site "
        "redesign, renamed classes, new banners). Fewer, targeted edits "
        "are better than a rewrite.\n"
        f"Current template:\n{json.dumps(old, ensure_ascii=False)}\n"
        f"Proof run of the current template:\n{report}"
    )


def plain_page(sysop, html, url):
    """Baseline build without a template — the yardstick preview()
    measures a draft against."""
    return sysop._build_with(html, url, None)


def build_with(sysop, html, url, template):
    """Builds a page from raw HTML, optionally with a template. Images
    stay off: the verification measures text, and re-fetching pictures
    for every draft would make learning unbearably slow."""
    from .page import build_page

    try:
        return build_page(html, url, render_images=False, template=template)
    except Exception:
        return None


def templater_registry(sysop, box):
    """The learning loop's tools — built in sysop_tools (see
    build_templater_registry)."""
    return build_templater_registry(box)
