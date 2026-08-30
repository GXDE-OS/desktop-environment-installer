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

from utils.translation import tr
from utils.get_input import (
  get_dir,
  get_int_with_bound_inclusive,
  get_yes_no_input,
)

INSTALLATION_REMOTE_BASE = "https://gitee.com/GXDE-OS/"
INSTALLATION_USE_SSH = False
WORKING_DIR = "./"

def init_installer() -> None:
  global INSTALLATION_REMOTE_BASE, INSTALLATION_USE_SSH, WORKING_DIR

  while True:
    print("")
    print(tr("Please choose from following repository sources:"))
    print(tr("  1. Gitee official"))
    print(tr("  2. GiHub official"))
    print(tr("  3. Manually entering mirror source"))

    source_choice = get_int_with_bound_inclusive("", 3, 1)

    if source_choice < 3:
      print(tr("Do you want to use SSH?"))
      installation_use_ssh = get_yes_no_input("")

      if source_choice == 1:
        if installation_use_ssh:
          installation_remote_base = "git@gitee.com:GXDE-OS/"
        else:
          installation_remote_base = "https://gitee.com/GXDE-OS/"
      else:
        if installation_use_ssh:
          installation_remote_base = "git@github.com:GXDE-OS/"
        else:
          installation_remote_base = "https://github.com/GXDE-OS/"
    else:
      print(tr("Third-party mirror sources are maintained by their respective "
        "providers and are not verified by the GXDE project. Before "
        "continuing, please make sure that you trust the selected source. "
        "The GXDE project is not responsible for issues caused by "
        "third-party sources."))
      proceed = get_yes_no_input(tr("Still proceed?"))
      if not proceed:
        continue

      print(tr("Please enter the mirror source URL."))
      print("  e.g. https://github.com/GXDE-OS/")
      print("  e.g. git@github.com:GXDE-OS/")
      installation_remote_base = input(tr("URL)> ")).strip()

      if not installation_remote_base.endswith("/"):
        installation_remote_base += "/"

      installation_use_ssh = installation_remote_base.startswith("git@")

    print(tr("We are now using: ") + installation_remote_base
      + tr("<REPO_NAME>"))
    print(tr("Is that correct?"))
    repo_confirm = get_yes_no_input("")
    if repo_confirm:
      INSTALLATION_REMOTE_BASE = installation_remote_base
      INSTALLATION_USE_SSH = installation_use_ssh
      break

  print("")
  WORKING_DIR = get_dir(
    tr("Please enter the working directory."),
    create_mode=True,
    must_empty=True,
  )

__all__ = ["init_installer"]
