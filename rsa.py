from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP

import os
from dotenv import load_dotenv
load_dotenv()

KEY_FOLDER_PATH = os.getenv('KEY_FOLDER_PATH')

# Generate a public/private key pair using the RSA module
# and store the private key in a PKCS#8 format.

def generate_key():
    # Check if key pair already exists
    private_key, public_key = read_key()
    if public_key is not None and private_key is not None:
        return private_key, public_key

    new_key = RSA.generate(2048)
    private_key = new_key.exportKey('PEM')
    public_key = new_key.publickey().exportKey('PEM')
    return private_key, public_key

def write_key(private_key, public_key):
    # Check if folder exitst
    if not os.path.exists(KEY_FOLDER_PATH):
        os.makedirs(KEY_FOLDER_PATH)

    with open(KEY_FOLDER_PATH + 'private.pem', 'wb') as f:
        f.write(private_key)
    with open(KEY_FOLDER_PATH + 'public.pem', 'wb') as f:
        f.write(public_key)

def read_key():
    if not os.path.exists(KEY_FOLDER_PATH):
        return None, None

    with open(KEY_FOLDER_PATH + 'private.pem', 'rb') as f:
        private_key = f.read()
    with open(KEY_FOLDER_PATH + 'public.pem', 'rb') as f:
        public_key = f.read()

    return private_key, public_key

def get_keys():
    private_key, public_key = read_key()
    if private_key is None or public_key is None:
        private_key, public_key = generate_key()
        write_key(private_key, public_key)
    return private_key, public_key

def decrypt(cipertext):
    private_key, public_key = read_key()
    if private_key is None:
        return None
    private_key = RSA.importKey(private_key)
    decryptor = PKCS1_OAEP.new(private_key)
    cipertext = bytes.fromhex(cipertext)
    return decryptor.decrypt(cipertext).decode('utf-8')

def encrypt(plaintext):
    private_key, public_key = read_key()
    if public_key is None:
        return None

    public_key = RSA.importKey(public_key)
    encryptor = PKCS1_OAEP.new(public_key)
    return encryptor.encrypt(bytes(plaintext, 'utf-8')).hex()

if __name__ == '__main__':
    private_key, public_key = get_keys()
    print(private_key)
    print(public_key)

    hash = encrypt("test:13435")
    print(hash)
    print(decrypt(hash))