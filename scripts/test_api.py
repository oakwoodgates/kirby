"""
Test script to verify API loads correctly.
"""

import sys

try:
    from src.api.main import app

    print("[OK] API loaded successfully")
    print("\nRegistered routes:")
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            methods = ','.join(route.methods) if route.methods else 'N/A'
            print(f"  [{methods:6}] {route.path}")

    print("\n[OK] All API routes registered successfully")
    sys.exit(0)

except Exception as e:
    print(f"[ERROR] Error loading API: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
