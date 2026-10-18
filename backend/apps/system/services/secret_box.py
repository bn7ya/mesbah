from __future__ import annotations

import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings

SALT: bytes = b"mesbah.system.secrets"
INFO: bytes = b"fernet-v1"


class SecretBox:
    def __init__(self, key_material: str | None = None) -> None:
        material: bytes = (key_material or settings.SECRET_KEY).encode()
        derived: bytes = HKDF(algorithm=hashes.SHA256(), length=32, salt=SALT, info=INFO).derive(
            material
        )
        self.fernet: Fernet = Fernet(base64.urlsafe_b64encode(derived))

    def seal(self, plain: str) -> str:
        return self.fernet.encrypt(plain.encode()).decode()

    def open(self, sealed: str) -> str | None:
        try:
            return self.fernet.decrypt(sealed.encode()).decode()
        except InvalidToken:
            return None
