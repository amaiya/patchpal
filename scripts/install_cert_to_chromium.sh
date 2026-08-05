#!/usr/bin/env bash
#
# Make Playwright's Chromium browser trust a corporate / self-signed CA by
# importing a CA bundle into the NSS database Chromium reads on Linux.
#
# This script does ALL steps:
#   1. Locate the CA bundle (arg, or $REQUESTS_CA_BUNDLE / $SSL_CERT_FILE)
#   2. Install the NSS tools (certutil) if missing
#   3. Initialize the NSS DB Chromium uses
#   4. Import every certificate in the bundle as a trusted CA
#
# Usage:
#   ./install_cert_to_chromium.sh [path-to-ca-bundle.pem]

set -euo pipefail

# ---------------------------------------------------------------------------
# 1. Locate the CA bundle
# ---------------------------------------------------------------------------
BUNDLE="${1:-${REQUESTS_CA_BUNDLE:-${SSL_CERT_FILE:-}}}"

if [[ -z "$BUNDLE" ]]; then
  echo "ERROR: No CA bundle specified." >&2
  echo "  Pass a path as the first argument, or set REQUESTS_CA_BUNDLE / SSL_CERT_FILE." >&2
  exit 1
fi
if [[ ! -r "$BUNDLE" ]]; then
  echo "ERROR: CA bundle not readable: $BUNDLE" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 2. Ensure certutil is available; install it if not.
# ---------------------------------------------------------------------------
install_certutil() {
  echo "'certutil' not found; attempting to install the NSS tools..."
  local sudo=""
  if [[ "$(id -u)" -ne 0 ]]; then
    if command -v sudo >/dev/null 2>&1; then
      sudo="sudo"
    else
      echo "ERROR: need root (or sudo) to install packages. Re-run as root, or install manually:" >&2
      echo "    apt install libnss3-tools   (Debian/Ubuntu)" >&2
      exit 1
    fi
  fi

  if command -v apt-get >/dev/null 2>&1; then
    $sudo apt-get update -qq
    $sudo apt-get install -y libnss3-tools
  elif command -v dnf >/dev/null 2>&1; then
    $sudo dnf install -y nss-tools
  elif command -v yum >/dev/null 2>&1; then
    $sudo yum install -y nss-tools
  elif command -v zypper >/dev/null 2>&1; then
    $sudo zypper install -y mozilla-nss-tools
  elif command -v pacman >/dev/null 2>&1; then
    $sudo pacman -Sy --noconfirm nss
  else
    echo "ERROR: could not detect a supported package manager." >&2
    echo "  Install the NSS tools (providing 'certutil') manually, then re-run." >&2
    exit 1
  fi
}

if ! command -v certutil >/dev/null 2>&1; then
  install_certutil
fi
if ! command -v certutil >/dev/null 2>&1; then
  echo "ERROR: 'certutil' still not found after install attempt." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 3. Locate / initialize the NSS DB Chromium uses
#    - Chromium M146+ default: $HOME/.local/share/pki/nssdb
#    - Older / if it already exists: $HOME/.pki/nssdb (Chromium prefers this)
# ---------------------------------------------------------------------------
if [[ -d "$HOME/.pki/nssdb" ]]; then
  NSSDB_DIR="$HOME/.pki/nssdb"
else
  NSSDB_DIR="$HOME/.local/share/pki/nssdb"
fi
mkdir -p "$NSSDB_DIR"
DB="sql:$NSSDB_DIR"

if [[ ! -f "$NSSDB_DIR/cert9.db" ]]; then
  certutil -d "$DB" -N --empty-password
fi

echo "Using NSS DB: $NSSDB_DIR"
echo "CA bundle:    $BUNDLE"

# ---------------------------------------------------------------------------
# 4. Split the bundle into individual certs (in a temp dir) and import each.
#    certutil imports one certificate per invocation.
# ---------------------------------------------------------------------------
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

# -s : suppress csplit's byte-count output ; -z : no empty leading file
csplit -sz -f "$TMPDIR/corpca-" "$BUNDLE" '/-----BEGIN CERTIFICATE-----/' '{*}'

count=0
imported=0
for f in "$TMPDIR"/corpca-*; do
  grep -q "BEGIN CERTIFICATE" "$f" || continue
  nickname="pp-ca-$count"
  if certutil -d "$DB" -A -t "C,," -n "$nickname" -i "$f" 2>/dev/null; then
    imported=$((imported + 1))
  else
    echo "  WARN: failed to import certificate #$count" >&2
  fi
  count=$((count + 1))
done

echo
echo "Imported $imported of $count certificate(s) into the NSS DB."
echo "Verify with:  certutil -d \"$DB\" -L"
echo "Now restart PatchPal and retry the browser tools."
