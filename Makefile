DOMAIN := desktop-environment-installer
PACKAGE := gxde-desktop-environment-installer
VERSION := 0.1.0
PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PYINSTALLER ?= $(PYTHON) -m PyInstaller
DIST_DIR := dist
BUILD_DIR := build/pyinstaller
BINARY := $(DIST_DIR)/$(PACKAGE)
POT_FILE := po/$(DOMAIN).pot
PO_FILES := $(wildcard po/*.po)
SOURCES := $(shell find src -type f -name '*.py' -print)

.DEFAULT_GOAL := package

.PHONY: package translations update-translations compile-translations test

package: compile-translations
	$(PYINSTALLER) \
		--noconfirm \
		--onefile \
		--name=$(PACKAGE) \
		--add-data="$(CURDIR)/locale:locale" \
		--distpath=$(DIST_DIR) \
		--workpath=$(BUILD_DIR) \
		--specpath=$(BUILD_DIR) \
		src/main.py
	@file $(BINARY)

translations: update-translations compile-translations

update-translations:
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

compile-translations:
	@for po_file in $(PO_FILES); do \
		language=$$(basename "$$po_file" .po); \
		target="locale/$$language/LC_MESSAGES/$(DOMAIN).mo"; \
		mkdir -p "$$(dirname "$$target")"; \
		msgfmt --check --check-accelerators --output-file="$$target" "$$po_file"; \
	done

test:
	$(PYTHON) -m unittest discover -s tests -v
