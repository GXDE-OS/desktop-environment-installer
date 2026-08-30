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

import os
from pathlib import Path
import shutil
import sys

from utils.translation import tr
from utils.get_input import (
  get_dir,
  get_int_with_bound_inclusive,
  get_yes_no_input,
)
from utils.git import git_clone
from utils.package_manager import get_pm_adapter
from definitions.modules import DTK2_MODULES, ModuleDefinition

INSTALLATION_REMOTE_BASE = "https://gitee.com/GXDE-OS/"
INSTALLATION_USE_SSH = False
WORKING_DIR = "./"
BUNDLE_ROOT = Path(
  getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent.parent)
)
INSTALLATION_SCRIPTS_DIR = BUNDLE_ROOT / "res" / "installation_scripts"

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

def repo_cat(repo_name: str) -> str:
  return INSTALLATION_REMOTE_BASE + repo_name

def repo_clone_dest_cat(repo_name: str) -> str:
  return WORKING_DIR + "/" + repo_name

def gen_artifact(module: ModuleDefinition) -> None:
  pm_adapter = get_pm_adapter()
  if pm_adapter is None:
    print(
      tr("Warning: no supported package manager adapter is available."),
      file=sys.stderr,
    )
    sys.exit(1)

  repo_name = module["repo_name"]
  display_name = module["display_name"]
  repo_dest = repo_clone_dest_cat(repo_name)
  clone_res = git_clone(
    repo_cat(repo_name),
    repo_dest,
    branch=module["branch"],
  )
  if not clone_res:
    print(tr("Failed to clone repository: ") + display_name)
    print(tr("Installation failed due to error occurred."))
    sys.exit(1)

  print(tr("Successfully cloned repository: ") + display_name)
  print(tr("Detected package manager: ") + pm_adapter.display_name)

  shutil.copytree(
    INSTALLATION_SCRIPTS_DIR,
    Path(repo_dest),
    dirs_exist_ok=True,
  )
  print(tr("Successfully generated installation scripts for repository: ")
    + display_name)

  build_pid = os.fork()
  if build_pid == 0:
    try:
      os.chdir(repo_dest)
      os.execvp(pm_adapter.build_command[0], list(pm_adapter.build_command))
    except OSError as error:
      print(
        tr("Failed to start package build: ") + str(error),
        file=sys.stderr,
        flush=True,
      )
      os._exit(1)

  _, build_status = os.waitpid(build_pid, 0)
  if os.waitstatus_to_exitcode(build_status) != 0:
    print(tr("Failed to build repository: ") + display_name)
    print(tr("Installation failed due to error occurred."))
    exit(1)

  print(tr("Successfully built repository: ") + display_name)

def install_current_stage(archive_name: str) -> None:
  pm_adapter = get_pm_adapter()
  if pm_adapter is None:
    print(
      tr("Warning: no supported package manager adapter is available."),
      file=sys.stderr,
    )
    sys.exit(1)

  archive_path = Path(archive_name)
  if (
      archive_path.is_absolute()
      or len(archive_path.parts) != 1
      or archive_name in {".", ".."}
    ):
    print(
      tr("Warning: invalid artifact archive name: ") + archive_name,
      file=sys.stderr,
    )
    sys.exit(1)

  artifacts_dir = (Path(WORKING_DIR) / "artifacts").resolve()
  try:
    packages = sorted({
      package.resolve()
      for pattern in pm_adapter.artifact_patterns
      for package in artifacts_dir.glob(pattern)
      if package.is_file()
    })
  except OSError as error:
    print(
      tr("Warning: failed to read the artifacts directory: ") + str(error),
      file=sys.stderr,
    )
    sys.exit(1)

  if not packages:
    print(
      tr("Warning: no package artifacts were found in: ")
      + str(artifacts_dir),
      file=sys.stderr,
    )
    sys.exit(1)

  try:
    install_pid = os.fork()
  except OSError as error:
    print(
      tr("Warning: failed to create the package installation process: ")
      + str(error),
      file=sys.stderr,
    )
    sys.exit(1)

  if install_pid == 0:
    try:
      install_command = [
        *pm_adapter.install_command,
        *(str(package) for package in packages),
      ]
      os.execvp(install_command[0], install_command)
    except OSError as error:
      print(
        tr("Warning: failed to start package installation: ") + str(error),
        file=sys.stderr,
        flush=True,
      )
      os._exit(1)

  try:
    _, install_status = os.waitpid(install_pid, 0)
  except OSError as error:
    print(
      tr("Warning: failed while waiting for package installation: ")
      + str(error),
      file=sys.stderr,
    )
    sys.exit(1)

  if os.waitstatus_to_exitcode(install_status) != 0:
    print(
      tr("Warning: failed to install the current stage: ") + archive_name,
      file=sys.stderr,
    )
    sys.exit(1)

  archive_dir = artifacts_dir / archive_name
  try:
    archive_dir.mkdir(exist_ok=True)
    for package in packages:
      package.replace(archive_dir / package.name)
  except OSError as error:
    print(
      tr("Warning: failed to archive installed packages: ")
      + str(error),
      file=sys.stderr,
    )
    sys.exit(1)

  print(tr("Successfully installed the current stage: ") + archive_name)
  print(tr("Archived installed packages in: ") + str(archive_dir))

def install_dtk2() -> None:
  print(tr("Installing dtk2 dependencies..."))
  for module in DTK2_MODULES:
    gen_artifact(module)
    print()
  install_current_stage("dtk2")

__all__ = ["init_installer"]
