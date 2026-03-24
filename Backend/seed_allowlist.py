"""
One-time script to seed the Firestore allowlist_domains collection
with authorized domains for magic-link authentication.

Safe to run multiple times (uses set with merge).
"""

import firebase_admin
from firebase_admin import firestore as fb_firestore

# Initialize Firebase Admin (uses Application Default Credentials)
if not firebase_admin._apps:
    firebase_admin.initialize_app()

DOMAINS = [
    "risalabs.ai",
    "asterahealthcare.org",
]


def seed_domains():
    fs = fb_firestore.client()
    for domain in DOMAINS:
        fs.collection("allowlist_domains").document(domain).set(
            {"allowed": True}, merge=True
        )
        print(f"✔ allowlist_domains/{domain} → allowed: true")


if __name__ == "__main__":
    seed_domains()
    print("\nDone. All domains seeded.")
