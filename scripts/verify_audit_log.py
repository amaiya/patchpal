#!/usr/bin/env python3
"""Verify audit log integrity by checking cryptographic hash chains.

Usage:
    python verify_audit_log.py ~/.patchpal/repos/<repo-name>/audit.log

This script verifies that audit log entries have not been tampered with
by checking the cryptographic hash chain (SHA-256). Each entry contains
a hash of its own contents and the hash of the previous entry, forming
an immutable ledger where modifying any entry breaks the entire chain.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path


def compute_hash(entry_dict: dict) -> str:
    """Compute SHA-256 hash of a log entry.

    Args:
        entry_dict: Log entry as dictionary (without hash field)

    Returns:
        Hex-encoded SHA-256 hash
    """
    # Create canonical JSON (sorted keys, no whitespace)
    canonical = json.dumps(entry_dict, sort_keys=True, separators=(",", ":"))

    # Compute SHA-256 hash
    hash_obj = hashlib.sha256(canonical.encode("utf-8"))

    return hash_obj.hexdigest()


def verify_entry(entry_dict: dict, expected_prev_hash: str | None) -> tuple[bool, str]:
    """Verify a single log entry's hash and chain linkage.

    Args:
        entry_dict: Log entry as dictionary (must include 'hash' field)
        expected_prev_hash: Expected value of prev_hash field (None for first entry)

    Returns:
        Tuple of (is_valid, entry_hash)
    """
    if "hash" not in entry_dict:
        return False, None

    # Extract hash and prev_hash
    stored_hash = entry_dict.pop("hash")
    stored_prev_hash = entry_dict.get("prev_hash")

    # Verify prev_hash matches expected
    if stored_prev_hash != expected_prev_hash:
        entry_dict["hash"] = stored_hash  # Restore
        return False, None

    # Compute expected hash
    expected_hash = compute_hash(entry_dict)

    # Restore hash to entry
    entry_dict["hash"] = stored_hash

    # Verify hash matches
    if stored_hash != expected_hash:
        return False, None

    return True, stored_hash


def verify_log_file(log_path: Path) -> dict:
    """Verify all entries in an audit log file.

    Args:
        log_path: Path to audit.log file

    Returns:
        Dictionary with verification statistics
    """
    if not log_path.exists():
        return {"error": f"Log file not found: {log_path}"}

    stats = {
        "total_entries": 0,
        "json_entries": 0,
        "verified": 0,
        "invalid": 0,
        "unhashed": 0,
        "sessions": {},
        "errors": [],
        "chains": [],  # List of (session_id, start_line, end_line, is_valid)
    }

    current_session = None
    current_chain = []
    prev_hash = None

    with open(log_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            stats["total_entries"] += 1

            # Skip non-JSON legacy log entries
            if not line.endswith("}"):
                continue

            # Extract JSON from log line (format: "timestamp - level - {json}")
            try:
                json_start = line.index('{"')
                json_str = line[json_start:]
                entry = json.loads(json_str)
            except (ValueError, json.JSONDecodeError) as e:
                stats["errors"].append(f"Line {line_num}: Failed to parse JSON: {e}")
                continue

            stats["json_entries"] += 1

            # Track sessions
            session_id = entry.get("session_id")
            if not session_id:
                stats["errors"].append(f"Line {line_num}: No session_id")
                continue

            # Check if this is a new session
            event_type = entry.get("event_type")
            if event_type == "SESSION_START":
                # Finalize previous chain if exists
                if current_chain:
                    stats["chains"].append(
                        {
                            "session_id": current_session,
                            "entries": len(current_chain),
                            "valid": all(current_chain),
                        }
                    )

                # Start new chain
                current_session = session_id
                current_chain = []
                prev_hash = None

                if session_id not in stats["sessions"]:
                    stats["sessions"][session_id] = {"start_line": line_num, "end_line": line_num}
                stats["sessions"][session_id]["start_line"] = line_num

            # Update session end line
            if session_id in stats["sessions"]:
                stats["sessions"][session_id]["end_line"] = line_num

            # Verify entry
            if "hash" not in entry:
                stats["unhashed"] += 1
                current_chain.append(False)
            else:
                is_valid, entry_hash = verify_entry(entry, prev_hash)

                if is_valid:
                    stats["verified"] += 1
                    current_chain.append(True)
                    prev_hash = entry_hash
                else:
                    stats["invalid"] += 1
                    current_chain.append(False)
                    stats["errors"].append(
                        f"Line {line_num}: Hash chain broken for {event_type} "
                        f"(session: {session_id[:8]}...)"
                    )
                    # Don't update prev_hash - chain is broken

    # Finalize last chain
    if current_chain:
        stats["chains"].append(
            {
                "session_id": current_session,
                "entries": len(current_chain),
                "valid": all(current_chain),
            }
        )

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Verify audit log integrity by checking cryptographic hash chains"
    )
    parser.add_argument(
        "log_file",
        type=Path,
        help="Path to audit.log file (e.g., ~/.patchpal/repos/<repo-name>/audit.log)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed errors")

    args = parser.parse_args()

    print(f"Verifying audit log: {args.log_file}")
    print("=" * 70)

    stats = verify_log_file(args.log_file)

    if "error" in stats:
        print(f"Error: {stats['error']}")
        return 1

    print(f"Total log entries:        {stats['total_entries']}")
    print(f"JSON entries:             {stats['json_entries']}")
    print(f"Sessions found:           {len(stats['sessions'])}")
    print()
    print(f"✅ Verified entries:      {stats['verified']}")
    print(f"❌ Invalid/broken chain:  {stats['invalid']}")
    print(f"⚠️  Unhashed entries:      {stats['unhashed']}")

    # Show chain status
    if stats["chains"]:
        print("\nHash Chains:")
        for chain in stats["chains"]:
            status = "✅ VALID" if chain["valid"] else "❌ BROKEN"
            print(f"  Session {chain['session_id'][:8]}...: {chain['entries']} entries - {status}")

    if stats["errors"]:
        print(f"\n⚠️  Errors encountered:    {len(stats['errors'])}")
        if args.verbose:
            print()
            for error in stats["errors"]:
                print(f"  • {error}")

    print()

    if stats["invalid"] > 0:
        print("🚨 WARNING: Log tampering detected! Hash chain is broken.")
        print("   This means one or more entries have been modified after creation.")
        return 2
    elif stats["verified"] == 0 and stats["json_entries"] > 0:
        print("⚠️  No entries could be verified (missing hash fields)")
        return 3
    else:
        print("✅ All hash chains are valid - no tampering detected.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
