"""
Secure Examination & Proctoring Platform
common/crypto_utils.py - RSA Digital Signatures, SHA-256 Hashing, and AES-256-GCM Encryption
"""

import base64
import hashlib
import os
from typing import Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def compute_sha256(data: bytes) -> str:
    """
    Computes SHA-256 hash of given byte sequence, returning hex string.
    """
    return hashlib.sha256(data).hexdigest()


def generate_rsa_keypair(key_size: int = 2048) -> Tuple[bytes, bytes]:
    """
    Generates an RSA keypair for digital signing and anti-repudiation.
    
    Returns:
        Tuple[bytes, bytes]: (private_key_pem, public_key_pem)
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend()
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    return private_pem, public_pem


def sign_data(private_key_pem: bytes, data: bytes) -> str:
    """
    Signs data using RSA Private Key with PSS padding and SHA-256.
    
    Returns:
        str: Base64-encoded signature string.
    """
    private_key = serialization.load_pem_private_key(
        private_key_pem,
        password=None,
        backend=default_backend()
    )

    signature = private_key.sign(
        data,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )

    return base64.b64encode(signature).decode("ascii")


def verify_signature(public_key_pem: bytes, data: bytes, signature_b64: str) -> bool:
    """
    Verifies an RSA signature against raw data using the corresponding Public Key.
    
    Returns:
        bool: True if signature is cryptographically valid, False otherwise.
    """
    try:
        public_key = serialization.load_pem_public_key(
            public_key_pem,
            backend=default_backend()
        )
        signature = base64.b64decode(signature_b64)

        public_key.verify(
            signature,
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except (InvalidSignature, ValueError, Exception):
        return False


def generate_aes_key() -> bytes:
    """
    Generates a secure 256-bit (32 bytes) symmetric key for AES-GCM.
    """
    return AESGCM.generate_key(bit_length=256)


def encrypt_aes_gcm(key: bytes, plaintext: bytes, associated_data: Optional[bytes] = None) -> bytes:
    """
    Encrypts plaintext using AES-256-GCM.
    
    Structure of returned bytes:
        [12 bytes Nonce] + [Ciphertext + 16 bytes Auth Tag]
    """
    nonce = os.urandom(12)  # 96-bit recommended nonce for GCM
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)
    return nonce + ciphertext


def decrypt_aes_gcm(key: bytes, payload: bytes, associated_data: Optional[bytes] = None) -> bytes:
    """
    Decrypts payload using AES-256-GCM.
    Expects first 12 bytes to be the Nonce.
    """
    if len(payload) < 28:  # 12 nonce + 16 tag minimum
        raise ValueError("Invalid AES-GCM payload: too short.")

    nonce = payload[:12]
    ciphertext = payload[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, associated_data)
