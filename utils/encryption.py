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
        else:
            # If it's a string, ensure it's properly formatted
            if isinstance(self.encryption_key, str):
                # Strip any whitespace and ensure proper encoding
                self.encryption_key = self.encryption_key.strip().encode('utf-8')
            
        try:
            self.fernet = Fernet(self.encryption_key)
        except Exception as e:
            print(f"Error initializing encryption with key: {e}")
            print("Generating new encryption key...")
            self.encryption_key = Fernet.generate_key()
            print(f"Generated new encryption key. Please save this in your .env file: ENCRYPTION_KEY={self.encryption_key.decode()}")
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