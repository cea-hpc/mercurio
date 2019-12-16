# This file is part of the RobinHood Library
# Copyright (C) 2019 Commissariat a l'energie atomique et aux energies
# 		      alternatives
#
# SPDX-License-Identifer: LGPL-3.0-or-later
#
# author: Quentin Bouget <quentin.bouget@cea.fr>

"""
Modest representations of ssh's public keys
"""

class PublicKey:
    """
    Modest representation of an ssh's public key

    If the implementation is tied to the format of keys generated with
    ssh-keygen it is only the consequence of the author's ignorance.
    Any contribution to standardize this representation is welcome.
    """
    # pylint: disable=too-few-public-methods

    SUPPORTED_FORMAT = (
        "ssh-rsa",
        "ssh-dss",
        "ssh-ed25519",
        "ecdsa-sha2-nistp256",
        "ecdsa-sha2-nistp384",
        "ecdsa-sha2-nistp521",
        )

    def __init__(self, header, key, *args, owner=None, origin=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.header = header
        self.key = key
        self.owner = owner
        self.origin = origin

    def __str__(self):
        comment = self.owner or ""
        if self.origin:
            comment = '@'.join((comment, self.origin))

        if comment:
            return ' '.join((self.header, self.key, comment))

        return ' '.join((self.header, self.key))

    @classmethod
    def from_line(cls, line, **kwargs):
        """
        Parse a public key from a string
        """
        try:
            header, key = line.split(maxsplit=1)
        except ValueError:
            raise ValueError("Unknown keyfile format '%s'" % line)

        if header not in cls.SUPPORTED_FORMAT:
            raise ValueError("Unrecognized keyfile header '%s'" % header)

        try:
            key, comment = key.split(maxsplit=1)
            try:
                owner, origin = comment.split('@')
            except ValueError:
                owner = comment
                origin = None
        except ValueError:
            owner = None
            origin = None

        return cls(header, key, owner=owner, origin=origin, **kwargs)


class AuthorizedKeyEntry:
    """
    Modest representation of an entry in an ssh's authorized_keys file
    """
    # pylint: disable=too-few-public-methods

    def __init__(self, publickey, options=None):
        self.publickey = publickey
        # Remove any empty string from the option list
        self.options = list(filter(bool, options or []))

    def __str__(self):
        return ' '.join((','.join(self.options), str(self.publickey))).lstrip()

    @classmethod
    def from_line(cls, line):
        """
        Parse an entry from an ssh's authorized_keys file
        """
        for header in PublicKey.SUPPORTED_FORMAT:
            options, header, line = line.rpartition(header)
            if not header:
                continue

            line = header + line
            options = options.strip().split(',')

            return cls(PublicKey.from_line(line), options=options)

        raise ValueError("Unrecognized entry format '%s'" % line)
