# author: Quentin Bouget <quentin.bouget@cea.fr>
#

"""
The different blocks used to build mercurio and the RsyncError class
"""

from collections import namedtuple
from os import strerror, walk
from pathlib import Path
from subprocess import DEVNULL, Popen

from parablox import ProcessBlock, ProcessingError


class RsyncError(OSError, ProcessingError):
    """
    To be raised when an RsyncBlock's rsync process fails
    """
    pass


RsyncUnit = namedtuple('RsyncUnit', ('source', 'destination'))
RsyncUnit.__doc__ = "Representation of a unit of transfer"


class FileFactory(ProcessBlock):
    """
    A ProcessBlock that iterates over a list of filepaths
    """

    def __init__(self, paths, *args, **kwargs):
        super().__init__(parent=None, *args, **kwargs)
        self.paths = [Path(path) for path in paths]
        self._gen = iter(self)

    def __iter__(self):
        """
        Yield files under self.paths (recursively)
        """
        for path in self.paths:
            try:
                path = path.resolve()
            except FileNotFoundError:
                self.logger.warning("'%s': no such file or directory", path)
                continue

            if path.is_file():
                yield RsyncUnit(str(path), "")
                continue

            # The pathlib lacks a recursive iterator (at least for now)
            # Fall back to using os.walk
            for root, _, files in walk(str(path)):
                root = Path(root)
                for filepath in files:
                    source = root / Path(filepath)
                    yield RsyncUnit(str(source),
                                    str(source.relative_to(path.parent).parent))

    def get_obj(self, timeout=None):
        """
        Get an object from the factory

        Set the stop event once every object is scheduled
        """
        try:
            return next(self._gen)
        except StopIteration:
            return None

    def process_obj(self, obj):
        return obj


class RsyncBlock(ProcessBlock):
    """
    Transfer one file at a time with rsync
    """

    def __init__(self, destination, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.destination = destination

    def process_obj(self, obj):
        destination = ''.join((self.destination, obj.destination))
        command = ["rsync", "-c", "--partial", obj.source, destination]
        proc = Popen(command, stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL)

        if proc.wait():
            raise RsyncError(proc.returncode, strerror(proc.returncode),
                             command)

        return obj
