"""Document ID generation for documents written through /doc/create."""

import secrets

# Marvin document IDs are drawn from an alphabet that omits visually ambiguous
# characters (0/O, 1/I/l, U/V).
_ID_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTWXYZabcdefghijkmnopqrstuvwxyz"

DEFAULT_ID_LENGTH = 20


def new_document_id(length: int = DEFAULT_ID_LENGTH) -> str:
    """Generate an ID in the format Marvin uses for its own documents.

    /doc/create does not generate IDs, so the caller supplies one.
    """
    if length <= 0:
        raise ValueError("length must be positive")
    return "".join(secrets.choice(_ID_ALPHABET) for _ in range(length))
