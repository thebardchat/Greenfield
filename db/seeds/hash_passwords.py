"""One-time script to hash seed user passwords with argon2.

Run after seeding: python db/seeds/hash_passwords.py
"""

import subprocess
import sys

# Ensure passlib + argon2 are available
try:
    from passlib.context import CryptContext
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "--break-system-packages", "passlib", "argon2-cffi"])
    from passlib.context import CryptContext

try:
    import asyncpg
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "--break-system-packages", "asyncpg"])
    import asyncpg

import asyncio

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

DEV_PASSWORD = "ClaimCruncher2026!"


async def main():
    conn = await asyncpg.connect(
        host="localhost", port=5433, user="claimcruncher",
        password="claimcruncher", database="claimcruncher",
    )
    hashed = pwd_context.hash(DEV_PASSWORD)
    result = await conn.execute(
        "UPDATE users SET password_hash = $1 WHERE password_hash LIKE '%SEEDHASH%'",
        hashed,
    )
    print(f"Updated passwords: {result}")
    print(f"Dev password for all users: {DEV_PASSWORD}")
    await conn.close()


asyncio.run(main())
