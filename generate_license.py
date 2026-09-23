import hashlib
import sys

# This MUST match the SECRET_SALT in the application!
SECRET_SALT = "LIT_MANAGER_SECRET_2026_xYz"

def generate_key(hardware_id):
    """Generate a license key based on the hardware ID and a secret salt."""
    raw_str = hardware_id.strip() + SECRET_SALT
    # Use SHA256 to create a secure hash
    full_hash = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
    # Return the first 16 characters as the license key (format: XXXX-XXXX-XXXX-XXXX)
    key = full_hash[:16].upper()
    return f"{key[:4]}-{key[4:8]}-{key[8:12]}-{key[12:16]}"

if __name__ == "__main__":
    print("=== Literature Manager License Generator ===")
    
    if len(sys.argv) > 1:
        hw_id = sys.argv[1]
    else:
        hw_id = input("Enter customer's Hardware ID: ").strip()
    
    if not hw_id:
        print("Error: Hardware ID cannot be empty.")
        sys.exit(1)
        
    license_key = generate_key(hw_id)
    print("\n------------------------------------------------")
    print(f"Hardware ID : {hw_id}")
    print(f"License Key : {license_key}")
    print("------------------------------------------------")
    print("Send this License Key to your customer.")
