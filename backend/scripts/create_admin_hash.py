"""Utility script to generate a secure bcrypt password hash for ADMIN_PASSWORD_HASH."""

import getpass
import sys
from app.core.security import hash_password


def main() -> None:
    """Prompt the developer for a password and print the bcrypt hash to set in .env."""
    print("=" * 60)
    print("HOTS Question Generator - Developer Password Hash Generator")
    print("=" * 60)
    
    password = getpass.getpass("Enter developer/admin password: ")
    if not password:
        print("Error: Password cannot be empty.", file=sys.stderr)
        sys.exit(1)
        
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Error: Passwords do not match.", file=sys.stderr)
        sys.exit(1)

    hashed = hash_password(password)
    print("\nGenerated bcrypt password hash:")
    print("-" * 60)
    print(f"ADMIN_PASSWORD_HASH={hashed}")
    print("-" * 60)
    print("Copy the line above into your backend/.env and .env files.\n")


if __name__ == "__main__":
    main()
