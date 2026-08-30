DOMAIN := desktop-environment-installer
PACKAGE := gxde-desktop-environment-installer
VERSION := 0.1.0
VENV_DIR := .venv
PYTHON ?= $(VENV_DIR)/bin/python
PYINSTALLER ?= $(PYTHON) -m PyInstaller
BUILD_ENV_STAMP := $(VENV_DIR)/.build-dependencies
DIST_DIR := dist
BUILD_DIR := build/pyinstaller
BINARY := $(DIST_DIR)/$(PACKAGE)
POT_FILE := po/$(DOMAIN).pot
PO_FILES := $(wildcard po/*.po)
SOURCES := $(shell find src -type f -name '*.py' -print)

.DEFAULT_GOAL := package

.PHONY: package translations update-translations compile-translations test \
	check-system-build-dependencies

package: check-system-build-dependencies $(BUILD_ENV_STAMP) compile-translations
	$(PYINSTALLER) \
		--noconfirm \
		--onefile \
		--name=$(PACKAGE) \
		--add-data="$(CURDIR)/locale:locale" \
		--add-data="$(CURDIR)/res/installation_scripts:res/installation_scripts" \
		--distpath=$(DIST_DIR) \
		--workpath=$(BUILD_DIR) \
		--specpath=$(BUILD_DIR) \
		src/main.py
	@file $(BINARY)

translations: update-translations compile-translations

check-system-build-dependencies:
	@missing=""; \
	for command in python3 msgfmt xgettext msgmerge file; do \
		if ! command -v "$$command" >/dev/null 2>&1; then \
			missing="$$missing $$command"; \
		fi; \
	done; \
	if [ -n "$$missing" ]; then \
		echo "Missing system build tools:$$missing" >&2; \
		echo "Ubuntu/Debian: sudo apt update && sudo apt install gettext python3-venv file" >&2; \
		exit 1; \
	fi

$(BUILD_ENV_STAMP): pyproject.toml uv.lock
	@if command -v uv >/dev/null 2>&1; then \
		uv sync --extra build; \
	else \
		if ! python3 -m venv "$(VENV_DIR)"; then \
			echo "Unable to create $(VENV_DIR)." >&2; \
			echo "Ubuntu/Debian: sudo apt install python3-venv" >&2; \
			exit 1; \
		fi; \
		"$(VENV_DIR)/bin/python" -m pip install '.[build]'; \
	fi
	@touch "$@"

update-translations: check-system-build-dependencies
	xgettext \
		--language=Python \
		--from-code=UTF-8 \
		--keyword=_ \
		--keyword=tr \
		--no-location \
		--package-name=$(PACKAGE) \
		--package-version=$(VERSION) \
		--output=$(POT_FILE) \
		$(SOURCES)
	@for po_file in $(PO_FILES); do \
		msgmerge --update --backup=none --no-location "$$po_file" "$(POT_FILE)"; \
	done

compile-translations: check-system-build-dependencies
	@for po_file in $(PO_FILES); do \
		language=$$(basename "$$po_file" .po); \
		target="locale/$$language/LC_MESSAGES/$(DOMAIN).mo"; \
		mkdir -p "$$(dirname "$$target")"; \
		msgfmt --check --check-accelerators --output-file="$$target" "$$po_file"; \
	done

test: $(BUILD_ENV_STAMP)
	$(PYTHON) -m unittest discover -s tests -v
