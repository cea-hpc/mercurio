# author: Quentin Bouget <quentin.bouget@cea.fr>
#

"""
Test the publickey module
"""

from io import BufferedIOBase
from os.path import join
from random import choice, randrange
from string import ascii_letters, digits, printable
from subprocess import check_call
from tempfile import TemporaryDirectory, TemporaryFile
from unittest import TestCase

from mercurio.publickey import AuthorizedKeyEntry, PublicKey

# A mapping of ssh-keygen algorithm and the corresponding header
KEYGEN_OPTIONS = {
    "ssh-rsa": ["-t", "rsa", "-b", "4096"],
    "ssh-dss": ["-t", "dsa", "-b", "1024"],
    "ssh-ed25519": ["-t", "ed25519", "-b", "4096"],
    "ecdsa-sha2-nistp256": ["-t", "ecdsa", "-b", "256"],
    "ecdsa-sha2-nistp384": ["-t", "ecdsa", "-b", "384"],
    "ecdsa-sha2-nistp521": ["-t", "ecdsa", "-b", "521"],
    }

def ssh_keygen(tmpdir, algo="ssh-ed25519", comment=""):
    """
    Generate a pair of keys under ``tmpdir`` using ssh-keygen
    """
    keypath = join(tmpdir, "id_" + algo.rsplit('-', maxsplit=1)[1])

    command = ["ssh-keygen", "-q", "-N", "", "-f", keypath, "-C", comment]
    command.extend(KEYGEN_OPTIONS[algo])

    check_call(command, cwd=tmpdir)

    return keypath + '.pub'

def publickey_from_file(keyfile):
    """
    Parse a PublicKey from the first line of a file-like object
    """
    line = keyfile.readline()
    if isinstance(keyfile, BufferedIOBase):
        line = line.decode()

    return PublicKey.from_line(line.strip())

def random_string(length, source):
    """
    Return a random string of ``length`` characters from ``source``
    """
    return ''.join(choice(source) for _ in range(randrange(length)))

def random_username():
    """
    Return a random username
    """
    username = random_string(30, source=ascii_letters + digits + '-_')
    # Because usernames are never empty, and mostly start with letters
    return choice(ascii_letters) + username

def random_hostname():
    """
    Return a random and valid hostname
    """
    hostname = random_string(254, source=ascii_letters + digits + '-')
    # From wikipedia: https://en.wikipedia.org/wiki/Hostname
    #   "hostnames are composed of ASCII letters 'a' through 'z' (in a
    #    case-insensitive manner), the digits '0' through '9', and the minus
    #    sign ('-'). The original specification of hostnames in
    #    [RFC 952](https://tools.ietf.org/html/rfc952), mandated that labels
    #    could not start with a digit or with a minus, and must not end with a
    #    minus sign. However, a subsequent specification
    #    [RFC 1123](https://tools.ietf.org/html/rfc1123) permitted hostname
    #    labels to start with digits. No other symbols, punctuation characters,
    #    or white space are permitted"
    return choice(ascii_letters + digits) + hostname.rstrip('-')

class TestPublicKey(TestCase):
    """
    Test the PublicKey class
    """

    def _test_format(self, algo="ssh-ed25519", owner=None, origin=None):
        """
        Generate a publickey and check it is correctly parsed
        """
        if owner:
            comment = owner
            if origin:
                comment = '@'.join((comment, origin))
        else:
            comment = ""

        with TemporaryDirectory() as tmpdir:
            keypath = ssh_keygen(tmpdir, algo, comment)

            with open(keypath, 'rb') as stream:
                line = stream.readline().decode().strip()
                publickey = PublicKey.from_line(line)

        if comment:
            key = line.rsplit(maxsplit=2)[-2]
        else:
            key = line.rsplit(maxsplit=1)[-1]

        self.assertEqual(publickey.header, algo)
        self.assertEqual(publickey.key, key)
        self.assertEqual(publickey.owner, owner)
        self.assertEqual(publickey.origin, origin)

        self.assertEqual(str(publickey), line)

        return publickey

    def test_bare(self):
        """
        Parse a key without comments
        """
        self._test_format()

    def test_with_owner(self):
        """
        Parse a key with a username in the comments
        """
        self._test_format(owner=random_username())

    def test_with_owner_and_origin(self):
        """
        Parse a key with a "username@hostname" comment
        """
        self._test_format(owner=random_username(), origin=random_hostname())

    def test_algorithm(self):
        """
        Parse public keys generated with supported algorithms
        """
        for algo in PublicKey.SUPPORTED_FORMAT:
            with self.subTest(algo=algo):
                self._test_format(algo=algo)

    def test_empty_file(self):
        """
        Parse an empty file
        """
        with TemporaryFile() as keyfile:
            with self.assertRaises(ValueError):
                publickey_from_file(keyfile)

    def test_not_a_publickey(self):
        """
        Parse a file that does not contain a public key
        """
        with TemporaryFile() as keyfile:
            keyfile.write(random_string(1 << 10, ascii_letters).encode())
            keyfile.seek(0)
            with self.assertRaises(ValueError):
                publickey_from_file(keyfile)

        with TemporaryFile() as keyfile:
            keyfile.write(random_string(1 << 10, printable).encode())
            keyfile.seek(0)
            with self.assertRaises(ValueError):
                publickey_from_file(keyfile)

    def test_probably_not_a_publickey(self):
        """
        Parse a file that sort of looks like a public key

        Admittedly, the content of the file looks nothing like a public
        key. The test is quite tied to the implementation of PublicKey.
        """
        with TemporaryFile() as keyfile:
            keyfile.write(b"ssh-blob blob blob@blob")
            keyfile.seek(0)
            with self.assertRaises(ValueError):
                publickey_from_file(keyfile)


class TestAuthorizedKey(TestCase):
    """
    Test the AuthorizedKey class
    """

    def test_from_publickey(self):
        """
        Create an AuthorizedKeyEntry from a publickey
        """
        with TemporaryDirectory() as tmpdir:
            keypath = ssh_keygen(tmpdir)
            with open(keypath) as keyfile:
                publickey = publickey_from_file(keyfile)

        entry = AuthorizedKeyEntry(publickey)

        self.assertEqual(entry.publickey, publickey)
        self.assertEqual(entry.options, [])
        self.assertEqual(str(entry), str(entry.publickey))

    def test_with_options(self):
        """
        Parse an AuthorizedKeyEntry prefixed with some options
        """
        options = ['command="/bin/rrsync ~/mercurio/%s' % random_username(),
                   "no-pty",
                   "no-X11-forwarding",
                   "no-port-forwarding"]

        with TemporaryDirectory() as tmpdir:
            keypath = ssh_keygen(tmpdir)

            with open(keypath, 'r+') as stream:
                line = ','.join(options) + ' ' + stream.readline().strip()

        entry = AuthorizedKeyEntry.from_line(line)
        self.assertEqual(entry.options, options)
        self.assertEqual(str(entry), line)

    def test_empty_file(self):
        """
        Parse an empty file
        """
        with TemporaryFile() as keyfile:
            with self.assertRaises(ValueError):
                AuthorizedKeyEntry.from_line(keyfile.readline().decode())
