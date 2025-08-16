from ecdsa import SigningKey, SECP256k1, VerifyingKey, BadSignatureError
from .utils import sha256, address_from_pubkey_hex, tx_message


class Wallet:
    def __init__(self, signing_key: SigningKey | None = None):
        self.sk = signing_key or SigningKey.generate(curve=SECP256k1)
        self.vk = self.sk.get_verifying_key()

    @property
    def private_key_hex(self) -> str:
        return self.sk.to_string().hex()

    @property
    def public_key_hex(self) -> str:
        return self.vk.to_string().hex()

    @property
    def address(self) -> str:
        return address_from_pubkey_hex(self.public_key_hex)

    def sign_transaction(self, sender: str, recipient: str, amount: int, nonce: int) -> str:
        msg = tx_message(sender, recipient, amount, nonce)
        sig = self.sk.sign_deterministic(msg)
        return sig.hex()


def verify_signature(pubkey_hex: str, signature_hex: str, sender: str, recipient: str, amount: int, nonce: int) -> bool:
    try:
        vk = VerifyingKey.from_string(bytes.fromhex(pubkey_hex), curve=SECP256k1)
        msg = tx_message(sender, recipient, amount, nonce)
        vk.verify(bytes.fromhex(signature_hex), msg)
        return True
    except BadSignatureError:
        return False
    except Exception:
        return False