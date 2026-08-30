# Copyright (C) 2026 CharOfString <root@charofstring.cc>
#
# This file is part of GXDE Desktop Environment Installer.
#
# GXDE Desktop Environment Installer is free software: you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the License,
# or (at your option) any later version.

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from git.exc import GitError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from utils import git as git_utils


class GitCloneTest(unittest.TestCase):
  def test_returns_true_when_clone_succeeds(self) -> None:
    with patch.object(git_utils.Repo, "clone_from") as clone_from:
      result = git_utils.git_clone(
        "https://example.com/repository.git",
        "/tmp/repository",
        branch="develop",
      )

    self.assertTrue(result)
    clone_from.assert_called_once_with(
      "https://example.com/repository.git",
      to_path="/tmp/repository",
      branch="develop",
    )

  def test_returns_false_for_empty_repository_or_destination(self) -> None:
    with patch.object(git_utils.Repo, "clone_from") as clone_from:
      self.assertFalse(git_utils.git_clone("", "/tmp/repository"))
      self.assertFalse(git_utils.git_clone("repository", ""))

    clone_from.assert_not_called()

  def test_returns_false_when_git_fails(self) -> None:
    output = StringIO()

    with patch.object(
        git_utils.Repo,
        "clone_from",
        side_effect=GitError("clone failed"),
      ), redirect_stdout(output):
      result = git_utils.git_clone("repository", "/tmp/repository")

    self.assertFalse(result)
    self.assertIn("clone failed", output.getvalue())

  def test_returns_false_when_file_system_operation_fails(self) -> None:
    output = StringIO()

    with patch.object(
        git_utils.Repo,
        "clone_from",
        side_effect=OSError("permission denied"),
      ), redirect_stdout(output):
      result = git_utils.git_clone("repository", "/tmp/repository")

    self.assertFalse(result)
    self.assertIn("permission denied", output.getvalue())


if __name__ == "__main__":
  unittest.main()
