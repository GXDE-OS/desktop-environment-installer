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

import shutil

from utils.translation import tr
from enum import Enum

class PackageManager(Enum):
  UNSUPPORTED = 0
  APT = 1

PM_CANDIDATES = {
  "apt": PackageManager.APT
}

CURRENT_PM = PackageManager.UNSUPPORTED

def init_pm_helper() -> None:
  for (cur, val) in PM_CANDIDATES.items():
    if shutil.which(cur):
      CURRENT_PM = val
      return

  print(tr("None of supported package managers were detected, halted!"))
  exit(126)

def get_pm() -> PackageManager:
  return CURRENT_PM

__all__ = ["PackageManager", "init_pm_helper", "get_pm"]
