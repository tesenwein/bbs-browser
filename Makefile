PYTHON ?= python3
VENV   := .venv
PIP    := $(VENV)/bin/pip
PY     := $(VENV)/bin/python
PREFIX ?= $(HOME)/.local/share/bbs-browser
BINDIR ?= $(HOME)/.local/bin

.PHONY: help venv test build install uninstall run clean

help: ## Diese Hilfe anzeigen
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

$(VENV)/bin/python:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -q --upgrade pip

venv: $(VENV)/bin/python ## Dev-Umgebung (.venv) mit allen Extras aufsetzen
	$(PIP) install -q -e ".[ai,firecrawl]"
	@$(PY) -m playwright install chromium >/dev/null 2>&1 \
		|| echo "Hinweis: Chromium-Download fehlgeschlagen - JS-Rendering bleibt aus"

test: venv ## Offline-Tests ausfuehren
	$(PY) tests/test_bbs.py

build: venv ## Wheel + sdist nach dist/ bauen
	$(PIP) install -q build
	$(PY) -m build

install: ## Als Kommando 'bbs' installieren (pipx oder eigenes venv, inkl. KI-SDK)
	@if command -v pipx >/dev/null 2>&1; then \
		pipx install --force . && pipx inject --force bbs-browser anthropic openai pyfiglet rich; \
	else \
		echo "pipx nicht gefunden - installiere nach $(PREFIX)"; \
		$(PYTHON) -m venv --clear $(PREFIX); \
		$(PREFIX)/bin/pip install -q --upgrade pip; \
		$(PREFIX)/bin/pip install -q ".[ai]"; \
		mkdir -p $(BINDIR); \
		ln -sf $(PREFIX)/bin/bbs $(BINDIR)/bbs; \
		echo "'bbs' installiert nach $(BINDIR)/bbs"; \
		case ":$$PATH:" in *":$(BINDIR):"*) ;; \
			*) echo "Hinweis: $(BINDIR) liegt nicht in PATH";; esac; \
	fi

uninstall: ## Installation entfernen (pipx oder eigenes venv)
	@if command -v pipx >/dev/null 2>&1 && pipx list --short 2>/dev/null | grep -q bbs-browser; then \
		pipx uninstall bbs-browser; \
	else \
		rm -f $(BINDIR)/bbs; rm -rf $(PREFIX); \
		echo "'bbs' entfernt"; \
	fi

run: venv ## Aus der Dev-Umgebung starten (make run URL=heise.de)
	$(PY) -m bbs_browser $(URL)

clean: ## Build-Artefakte und Dev-Umgebung entfernen
	rm -rf build dist *.egg-info $(VENV)
	find . -name __pycache__ -type d -exec rm -rf {} +
