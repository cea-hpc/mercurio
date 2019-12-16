# This file is part of the RobinHood Library
# Copyright (C) 2019 Commissariat a l'energie atomique et aux energies
# 		      alternatives
#
# SPDX-License-Identifer: LGPL-3.0-or-later
#
# author: Quentin Bouget <quentin.bouget@cea.fr>

"""
Test the different block classes defined in mercurio.blocks
"""

from logging import WARNING
from os.path import exists, join
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from unittest import TestCase

from mercurio.blocks import FileFactory, RsyncBlock, RsyncError, RsyncUnit


class TestFileFactory(TestCase):
    """
    Test the FileFactory class
    """

    def test_iter_files(self):
        """
        FileFactory iterates over paths that are files
        """
        with TemporaryDirectory() as tmpdir:
            try:
                tempfiles = [NamedTemporaryFile(dir=tmpdir) for _ in range(10)]
                paths = [Path(file_.name) for file_ in tempfiles]
                units = [RsyncUnit(str(path), "") for path in paths]
                self.assertCountEqual(FileFactory(paths), units)
            finally:
                for file_ in tempfiles:
                    file_.close()

    def test_iter_dir(self):
        """
        FileFactory recursively iterates over paths that are directories
        """
        with TemporaryDirectory() as tmpdir:
            try:
                tempfiles = [NamedTemporaryFile(dir=tmpdir) for _ in range(10)]
                tmpdir = Path(tmpdir)
                paths = [Path(file_.name) for file_ in tempfiles]
                units = [RsyncUnit(str(path), tmpdir.name) for path in paths]
                self.assertCountEqual(FileFactory([tmpdir]), units)
            finally:
                for file_ in tempfiles:
                    file_.close()

    def test_empty_directory(self):
        """
        Iterating on an empty directory yield no RsyncUnit
        """
        with TemporaryDirectory() as tmpdir:
            self.assertCountEqual(FileFactory([tmpdir]), [])

    def test_warning_on_missing_path(self):
        """
        FileFactory logs a warning when one of its path does not exist
        """
        path = "missing_file_or_dir"
        with self.assertLogs(level=WARNING) as context_manager:
            list(FileFactory([path]))
        self.assertIn(path, context_manager.output[0])

    def test_get_obj(self):
        """
        FileFactory is a "block-iterator"
        """
        with TemporaryDirectory() as tmpdir:
            try:
                tempfiles = [NamedTemporaryFile(dir=tmpdir) for _ in range(10)]
                file_factory = FileFactory([tmpdir])

                units = list(file_factory)
                for _ in file_factory:
                    unit = file_factory.get_obj()
                    self.assertIn(unit, units)
                    units.remove(unit)
                self.assertIsNone(file_factory.get_obj())
            finally:
                for file_ in tempfiles:
                    file_.close()

    def test_process_obj(self):
        """
        FileFactory does not modify the element it iterates over
        """
        obj = object()
        self.assertEqual(FileFactory([]).process_obj(obj), obj)


class TestRsyncBlock(TestCase):
    """
    Test the RsyncBlock class
    """

    def test_rsync_one(self):
        """
        RsyncBlock sends/copies files
        """
        with TemporaryDirectory() as tmpdir:
            rsync_block = RsyncBlock(tmpdir)

            with NamedTemporaryFile() as tmpfile:
                rsync_block.process_obj(RsyncUnit(tmpfile.name, ""))
                self.assertTrue(exists(join(tmpdir, tmpfile.name)))

    def test_missing_source_file(self):
        """
        An RsyncError is raised if the source file is missing
        """
        with TemporaryDirectory() as tmpdir:
            rsync_block = RsyncBlock(tmpdir)

            missing_file = join(tmpdir, "missing_file")
            with self.assertRaises(RsyncError):
                rsync_block.process_obj(RsyncUnit(missing_file, ""))
