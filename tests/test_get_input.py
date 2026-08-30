# Copyright (C) 2026 CharOfString <root@charofstring.cc>
#
# This file is part of GXDE Desktop Environment Installer.
#
# GXDE Desktop Environment Installer is free software: you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the License,
# or (at your option) any later version.

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from utils.get_input import get_dir


class GetDirTest(unittest.TestCase):
  def test_returns_absolute_path_for_relative_input(self) -> None:
    with patch("builtins.input", return_value="."):
      result = get_dir("", create_mode=False, must_empty=False)

    self.assertTrue(Path(result).is_absolute())
    self.assertEqual(Path.cwd().resolve(), Path(result))

  def test_accepts_existing_directory(self) -> None:
    with TemporaryDirectory() as temporary_directory, \
        patch("builtins.input", return_value=temporary_directory):
      self.assertEqual(
        temporary_directory,
        get_dir("", create_mode=False, must_empty=True),
      )

  def test_creates_missing_directory_and_its_parents(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      target = Path(temporary_directory) / "parent" / "target"

      with patch("builtins.input", return_value=str(target)):
        result = get_dir("", create_mode=True, must_empty=True)

      self.assertEqual(str(target), result)
      self.assertTrue(target.is_dir())

  def test_rejects_missing_directory_when_creation_is_disabled(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      missing = Path(temporary_directory) / "missing"

      with patch(
          "builtins.input",
          side_effect=[str(missing), temporary_directory],
        ):
        result = get_dir("", create_mode=False, must_empty=False)

      self.assertEqual(temporary_directory, result)
      self.assertFalse(missing.exists())

  def test_rejects_regular_file(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      file_path = Path(temporary_directory) / "file"
      file_path.touch()

      with patch(
          "builtins.input",
          side_effect=[str(file_path), temporary_directory],
        ):
        result = get_dir("", create_mode=True, must_empty=False)

      self.assertEqual(temporary_directory, result)

  def test_rejects_non_empty_directory_when_empty_is_required(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      non_empty = Path(temporary_directory) / "non-empty"
      non_empty.mkdir()
      (non_empty / "file").touch()
      empty = Path(temporary_directory) / "empty"
      empty.mkdir()

      with patch(
          "builtins.input",
          side_effect=[str(non_empty), str(empty)],
        ):
        result = get_dir("", create_mode=False, must_empty=True)

      self.assertEqual(str(empty), result)

  def test_accepts_non_empty_directory_when_empty_is_not_required(self) -> None:
    with TemporaryDirectory() as temporary_directory:
      (Path(temporary_directory) / "file").touch()

      with patch("builtins.input", return_value=temporary_directory):
        result = get_dir("", create_mode=False, must_empty=False)

      self.assertEqual(temporary_directory, result)


if __name__ == "__main__":
  unittest.main()
