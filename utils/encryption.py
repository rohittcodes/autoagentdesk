from cryptography.fernet import Fernet
from typing import Dict
import os
import json
from base64 import b64encode
import hashlib

class CredentialManager:
    def __init__(self):
        # Generate or load encryption key
        self.encryption_key = os.getenv('ENCRYPTION_KEY')
        if not self.encryption_key:
            self.encryption_key = Fernet.generate_key()
            print(f"Generated new encryption key. Please save this in your .env file: ENCRYPTION_KEY={self.encryption_key.decode()}")
        elif isinstance(self.encryption_key, str):
            self.encryption_key = self.encryption_key.encode()
            
        self.fernet = Fernet(self.encryption_key)
    
    def encrypt_credentials(self, credentials: Dict[str, str]) -> str:
        """Encrypt AWS credentials"""
        # Convert credentials to JSON string
        cred_json = json.dumps(credentials)
        # Encrypt the JSON string
        encrypted_data = self.fernet.encrypt(cred_json.encode())
        return encrypted_data.decode()
    
    def decrypt_credentials(self, encrypted_data: str) -> Dict[str, str]:
        """Decrypt AWS credentials"""
        try:
            # Decrypt the data
            decrypted_data = self.fernet.decrypt(encrypted_data.encode())
            # Parse JSON string back to dictionary
            return json.loads(decrypted_data.decode())
        except Exception as e:
            raise ValueError(f"Failed to decrypt credentials: {str(e)}")
    
    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Create a hash of the API key for storage"""
        return hashlib.sha256(api_key.encode()).hexdigest()