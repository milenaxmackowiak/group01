from cryptography.fernet import Fernet, InvalidToken

f = Fernet(Fernet.generate_key())

try:
    f.decrypt(b"not a valid fernet token at all")
except Exception as e:
    print(type(e).__name__, ":", e)