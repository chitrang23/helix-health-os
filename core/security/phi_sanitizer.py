import re
import os
import uuid
from typing import Tuple, Dict
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class ZeroTrustPHIBroker:
    def __init__(self, master_key: bytes = None):
        self.key = master_key or AESGCM.generate_key(bit_length=256)
        self.aesgcm = AESGCM(self.key)

    def redact_phi(self, text: str) -> Tuple[str, Dict[str, str]]:
        token_map = {}
        phone_pattern = r"\b(?:\+91|0)?[6-9]\d{9}\b"
        abha_pattern = r"\b\d{2}-\d{4}-\d{4}-\d{4}\b"
        
        def tokenize(match, prefix):
            token = f"<{prefix}_{uuid.uuid4().hex[:6]}>"
            token_map[token] = match.group(0)
            return token

        sanitized = re.sub(phone_pattern, lambda m: tokenize(m, "PHONE"), text)
        sanitized = re.sub(abha_pattern, lambda m: tokenize(m, "ABHA"), sanitized)
        return sanitized, token_map

    def encrypt_field(self, plaintext: str) -> bytes:
        nonce = os.urandom(12)
        ciphertext = self.aesgcm.encrypt(nonce, plaintext.encode(), None)
        return nonce + ciphertext

    def decrypt_field(self, payload: bytes) -> str:
        nonce = payload[:12]
        ciphertext = payload[12:]
        return self.aesgcm.decrypt(nonce, ciphertext, None).decode()
