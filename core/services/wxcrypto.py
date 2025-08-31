import base64
from Crypto.Cipher import AES

class WxCrypto:
    @staticmethod
    def _unpad(s: bytes) -> bytes:
        pad = s[-1]
        return s[:-pad]

    @staticmethod
    def decrypt(encryptedData: str, session_key: str, iv: str) -> dict:
        # all inputs are base64 strings
        _data = base64.b64decode(encryptedData)
        _key = base64.b64decode(session_key + '==')  # auto pad
        _iv = base64.b64decode(iv + '==')
        cipher = AES.new(_key, AES.MODE_CBC, _iv)
        raw = cipher.decrypt(_data)
        # PKCS#7 unpad
        raw = WxCrypto._unpad(raw)
        import json
        return json.loads(raw.decode('utf-8', errors='ignore'))
