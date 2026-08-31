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

from git.exc import GitError
from git.repo import Repo

from .translation import tr

def git_clone(repo: str, dest: str, branch: str = "master") -> bool:
  if repo == "" or dest == "":
    return False

  original_directory: Path | None = None
  try:
    try:
      original_directory = Path.cwd()
    except OSError:
      # The installer may have been updated by replacing the directory from
      # which an older process was launched. Recover by entering the stable
      # parent of the absolute clone destination before Git starts.
      pass

    os.chdir(Path(dest).expanduser().parent)
    Repo.clone_from(repo, to_path=dest, branch=branch)
  except (GitError, OSError) as error:
    print(tr("Git clone failed: ") + str(error))
    return False
  finally:
    if original_directory is not None:
      try:
        os.chdir(original_directory)
      except OSError:
        pass

  return True
