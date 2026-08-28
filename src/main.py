# Copyright (C) 2026 CharOfString <root@charofstring.cc>
#
# This file is part of GXDE Desktop Environment Installer.
#
# GXDE Desktop Environment Installer is free software: you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the License,
# or (at your option) any later version.
#
# GXDE Desktop Environment Installer is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# GXDE Desktop Environment Installer.If not,
# see <https://www.gnu.org/licenses/>.

import gettext
from pathlib import Path
import sys

DOMAIN = "desktop-environment-installer"
DEFAULT_LANGUAGE = "en_US"
BUNDLE_ROOT = Path(
  getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)
)
LOCALE_DIR = BUNDLE_ROOT / "locale"

def get_translator(language: str | None = None) -> gettext.NullTranslations:
  languages = [language] if language else None
  try:
    return gettext.translation(
      DOMAIN,
      localedir=LOCALE_DIR,
      languages=languages,
    )
  except FileNotFoundError:
    return gettext.translation(
      DOMAIN,
      localedir=LOCALE_DIR,
      languages=[DEFAULT_LANGUAGE],
      fallback=True,
    )

_ = get_translator().gettext

def main() -> None:
  print(_("GXDE Desktop Environment Installer"))

if __name__ == "__main__":
  main()
