from utils.encryption import CredentialManager
import secrets

def generate_keys():
    # Generate a random API key
    api_key = secrets.token_urlsafe(32)
    
    # Create credential manager (this will generate an encryption key)
    cred_manager = CredentialManager()
    
    # Get the API key hash
    api_key_hash = cred_manager.hash_api_key(api_key)
    
    print("\nAdd these to your .env file:")
    print(f"ENCRYPTION_KEY={cred_manager.encryption_key.decode()}")
    print(f"API_KEY_HASH={api_key_hash}")
    print(f"\nStore this API key securely (this is what you'll use in API requests):")
    print(f"API_KEY={api_key}")

if __name__ == "__main__":
    generate_keys()