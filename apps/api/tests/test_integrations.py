import unittest

from app.services.credentials import CredentialCipher


class CredentialTest(unittest.TestCase):
    def test_encrypt_round_trip_does_not_store_plaintext(self) -> None:
        cipher = CredentialCipher("test-encryption-key")
        ciphertext, nonce = cipher.encrypt({"api_key": "secret-value"})
        self.assertNotIn("secret-value", ciphertext)
        self.assertEqual(cipher.decrypt(ciphertext, nonce)["api_key"], "secret-value")


if __name__ == "__main__":
    unittest.main()
