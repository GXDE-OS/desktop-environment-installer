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

import sys

from pathlib import Path
from utils.get_input import get_yes_no_input
from utils.translation import tr
from utils.package_manager import init_pm_helper
from core.installer import init_installer

DOMAIN = "desktop-environment-installer"
DEFAULT_LANGUAGE = "en_US"
BUNDLE_ROOT = Path(
  getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)
)
LOCALE_DIR = BUNDLE_ROOT / "locale"
INSTALLER_VERSION = "0.1.0"

def main() -> None:
  print(tr("GXDE Desktop Environment Installer"))
  print(f"RELEASE v{INSTALLER_VERSION}")
  print("=========================================================")
  print(tr("Please ensure that you have NOT installed Deepin DDE..."))
  print(tr("For GXDE relys on old version of DDE components, "
    "which may be conflict with Deepin DDE."))
  print(tr("If you have installed UKUI Wayland session then you may only use "
    "GXDE X11 session..."))
  print(tr("For GXDE's Wayland compositor is based on Kylin's Wayland "
    "compositor, which may be conflict with UKUI Wayland compositor."))

  proceed = get_yes_no_input(tr("Still proceed with the installation?"))
  if not proceed:
    print(tr("You have chosen to exit the installation process."))
    sys.exit(0)

  init_pm_helper()
  init_installer()
  print()

if __name__ == "__main__":
  main()
