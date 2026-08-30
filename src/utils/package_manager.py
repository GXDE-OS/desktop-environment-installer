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

from dataclasses import dataclass
from enum import Enum
import shutil

from utils.translation import tr

class PackageManager(Enum):
  UNSUPPORTED = 0
  APT = 1

@dataclass(frozen=True)
class PackageManagerAdapter:
  detection_command: str
  display_name: str
  build_command: tuple[str, ...]
  artifact_patterns: tuple[str, ...]
  install_command: tuple[str, ...]

PM_ADAPTERS = {
  PackageManager.APT: PackageManagerAdapter(
    detection_command="apt",
    display_name="Advanced Packaging Tools",
    build_command=("./gxde_build_deb.sh", "-d"),
    artifact_patterns=("*.deb",),
    install_command=("sudo", "apt", "install"),
  ),
}

PM_CANDIDATES = {
  adapter.detection_command: package_manager
  for package_manager, adapter in PM_ADAPTERS.items()
}

CURRENT_PM = PackageManager.UNSUPPORTED

def init_pm_helper() -> None:
  global CURRENT_PM

  for (cur, val) in PM_CANDIDATES.items():
    if shutil.which(cur):
      CURRENT_PM = val
      return

  print(tr("None of supported package managers were detected, halted!"))
  exit(126)

def get_pm() -> PackageManager:
  return CURRENT_PM

def get_pm_adapter() -> PackageManagerAdapter | None:
  return PM_ADAPTERS.get(CURRENT_PM)

__all__ = [
  "PackageManager",
  "PackageManagerAdapter",
  "init_pm_helper",
  "get_pm",
  "get_pm_adapter",
]
