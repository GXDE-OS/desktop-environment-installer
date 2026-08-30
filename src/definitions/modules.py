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

from typing import TypedDict


class ModuleDefinition(TypedDict):
  repo_name: str
  display_name: str
  branch: str


DTK2_MODULES: list[ModuleDefinition] = [
  {
    "repo_name": "dtk2widget-qt6",
    "display_name": "DTK2-Widget (Qt6 port)",
    "branch": "qt6",
  },
  {
    "repo_name": "gxde-qt6-integration",
    "display_name": "DTK2-Widget integration (Qt6 port)",
    "branch": "qt6",
  },
]
