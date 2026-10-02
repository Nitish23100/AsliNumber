"""Argon2id password hashing and verification.

Uses ``pwdlib[argon2]``'s recommended configuration, which hashes with
Argon2 in its ``argon2id`` variant (memory-hard, resistant to both
GPU-cracking and side-channel attacks). Each call to :func:`hash_password`
generates a fresh random salt, so hashing the same plaintext twice yields
two different hash strings even though both verify successfully against
that same plaintext.
"""

from pwdlib import PasswordHash

# A single, process-wide PasswordHash instance. ``PasswordHash.recommended()``
# currently resolves to an Argon2Hasher (argon2id) with pwdlib/argon2-cffi's
# default cost parameters.
_password_hash = PasswordHash.recommended()


def hash_password(plaintext: str) -> str:
    """Hash ``plaintext`` into an argon2id hash string suitable for storage.

    Args:
        plaintext: The password to hash.

    Returns:
        An encoded argon2id hash string (includes algorithm, cost
        parameters, salt, and digest). Never equal to ``plaintext``.
    """
    return _password_hash.hash(plaintext)


def verify_password(plaintext: str, stored_hash: str) -> bool:
    """Verify ``plaintext`` against a previously stored argon2id hash.

    Returns ``True``/``False`` for a well-formed hash; never raises on a
    simple password mismatch. Only raises ``pwdlib.exceptions.UnknownHashError``
    if ``stored_hash`` is not a hash this module's hasher recognizes (e.g. a
    corrupt or non-argon2 value), since there is no valid True/False answer
    for a hash pwdlib cannot parse.

    Args:
        plaintext: The password to check.
        stored_hash: The previously stored hash to verify against.

    Returns:
        ``True`` if ``plaintext`` matches ``stored_hash``, ``False`` otherwise.
    """
    return _password_hash.verify(plaintext, stored_hash)
