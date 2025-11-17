#!/usr/bin/env python3
"""Diagnostic script to check exports directory configuration."""

import os
import sys
from pathlib import Path

def check_exports_directory():
    """Check if exports directory is properly configured."""

    print("="*60)
    print("Exports Directory Diagnostic")
    print("="*60)
    print()

    # Expected export path
    export_path = Path("/app/exports")

    # Check if directory exists
    print(f"1. Checking if {export_path} exists...")
    if export_path.exists():
        print(f"   ✅ Directory exists")
    else:
        print(f"   ❌ Directory does NOT exist")
        print(f"   This means the bind mount is not working!")
        return False
    print()

    # Check if it's a directory
    print(f"2. Checking if {export_path} is a directory...")
    if export_path.is_dir():
        print(f"   ✅ Is a directory")
    else:
        print(f"   ❌ Exists but is NOT a directory")
        return False
    print()

    # Check read permissions
    print(f"3. Checking read permissions...")
    if os.access(export_path, os.R_OK):
        print(f"   ✅ Directory is readable")
    else:
        print(f"   ❌ Directory is NOT readable")
        return False
    print()

    # Check write permissions
    print(f"4. Checking write permissions...")
    if os.access(export_path, os.W_OK):
        print(f"   ✅ Directory is writable")
    else:
        print(f"   ❌ Directory is NOT writable")
        print(f"   This is likely a permissions issue!")
        return False
    print()

    # Check execute permissions (needed to list directory)
    print(f"5. Checking execute permissions...")
    if os.access(export_path, os.X_OK):
        print(f"   ✅ Directory is executable (can list contents)")
    else:
        print(f"   ❌ Directory is NOT executable")
        return False
    print()

    # Get directory stats
    print(f"6. Directory permissions and ownership...")
    stats = export_path.stat()
    print(f"   Mode: {oct(stats.st_mode)}")
    print(f"   UID: {stats.st_uid}")
    print(f"   GID: {stats.st_gid}")
    print()

    # Check current user
    print(f"7. Current process user...")
    print(f"   UID: {os.getuid()}")
    print(f"   GID: {os.getgid()}")
    print(f"   Groups: {os.getgroups()}")
    print()

    # Try to list contents
    print(f"8. Listing directory contents...")
    try:
        contents = list(export_path.iterdir())
        print(f"   ✅ Successfully listed {len(contents)} items")
        if contents:
            for item in contents[:5]:  # Show first 5
                print(f"      - {item.name}")
            if len(contents) > 5:
                print(f"      ... and {len(contents) - 5} more")
    except PermissionError as e:
        print(f"   ❌ Permission denied: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Error listing directory: {e}")
        return False
    print()

    # Try to create a test file
    print(f"9. Testing file creation...")
    test_file = export_path / ".test_write_permissions"
    try:
        test_file.write_text("test")
        print(f"   ✅ Successfully created test file")
        # Clean up
        test_file.unlink()
        print(f"   ✅ Successfully deleted test file")
    except PermissionError as e:
        print(f"   ❌ Permission denied when writing: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Error creating test file: {e}")
        return False
    print()

    # Check mount point
    print(f"10. Checking if this is a mount point...")
    with open('/proc/mounts', 'r') as f:
        mounts = f.read()
        if '/app/exports' in mounts:
            print(f"   ✅ Found in /proc/mounts")
            for line in mounts.split('\n'):
                if '/app/exports' in line:
                    print(f"      {line}")
        else:
            print(f"   ⚠️  Not found in /proc/mounts")
            print(f"      This might be normal if using bind mount")
    print()

    print("="*60)
    print("✅ All checks passed! Exports directory is properly configured.")
    print("="*60)
    return True


if __name__ == "__main__":
    success = check_exports_directory()
    sys.exit(0 if success else 1)
