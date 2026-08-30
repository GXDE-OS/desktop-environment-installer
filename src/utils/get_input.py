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

from pathlib import Path

from .translation import tr

def get_yes_no_input(prompt: str) -> bool:
  while True:
    if prompt == "":
      user_input = input("(y/n)> ").strip().lower()
    else:
      user_input = input(prompt + " (y/n)> ").strip().lower()
    if user_input in ("y", "yes"):
      return True
    elif user_input in ("n", "no"):
      return False
    else:
      print(tr("Invalid input. Please try again."))

def get_int(prompt: str) -> int:
  while True:
    user_input = input(prompt + " (INT)> ").strip()
    try:
      res = int(user_input)
      return res
    except:
      print(tr("Invalid input. Please try again."))

def get_int_with_bound_inclusive(prompt: str, upper: int, lower: int) -> int:
  while True:
    hint = prompt + " (" + str(lower) + " <= INT <= " + str(upper) + ")> "
    user_input = input(hint).strip()
    try:
      res = int(user_input)
      if res > upper:
        print(tr("The integer you have input exceeded the range required, "
          "please try again."))
      elif res < lower:
        print(tr("The integer you have input exceeded the range required, "
          "please try again."))
      else:
        return res
    except:
      print(tr("Invalid input. Please try again."))

def get_dir(prompt: str, create_mode: bool, must_empty: bool) -> str:
  while True:
    if prompt == "":
      user_input = input(tr("(DIR)> ")).strip()
    else:
      user_input = input(prompt + " " + tr("(DIR)> ")).strip()

    if user_input.startswith("'") and user_input.endswith("'"):
      user_input = user_input[1:-1]

    if user_input.startswith('"') and user_input.endswith('"'):
      user_input = user_input[1:-1]

    if user_input == "":
      print(tr("Invalid input. Please try again."))
      continue

    try:
      directory = Path(user_input).expanduser()
    except (OSError, RuntimeError):
      print(tr("Invalid directory path. Please try again."))
      continue

    if directory.exists():
      if not directory.is_dir():
        print(tr("The path is not a directory. Please try again."))
        continue
    elif not create_mode:
      print(tr("The directory does not exist. Please try again."))
      continue
    else:
      try:
        directory.mkdir(parents=True)
      except OSError as error:
        print(tr("Failed to create the directory: ") + str(error))
        continue

    if must_empty:
      try:
        if any(directory.iterdir()):
          print(tr("The directory is not empty. Please try again."))
          continue
      except OSError as error:
        print(tr("Failed to access the directory: ") + str(error))
        continue

    return str(directory.resolve())

__all__ = [
  "get_yes_no_input",
  "get_int",
  "get_int_with_bound_inclusive",
  "get_dir"
]
