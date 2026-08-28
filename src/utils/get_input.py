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

from .translation import tr

def get_yes_no_input(prompt: str) -> bool:
  while True:
    user_input = input(prompt + " (y/n)> ").strip().lower()
    if user_input in ("y", "yes"):
      return True
    elif user_input in ("n", "no"):
      return False
    else:
      print(tr("Invalid input. Please try again."))

__all__ = ["get_yes_no_input"]
