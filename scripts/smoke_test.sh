#!/usr/bin/env bash
# ==============================================================================
# End-to-End Smoke Test (Local Docker Compose & Azure Deployment)
# ==============================================================================
# Tests:
#   1. Plain HTTP -> HTTPS redirect (Measure of Success M2)
#   2. File upload   (POST /api/files)
#   3. File listing  (GET /api/files)
#   4. File download (GET /api/files/{id}/download) + SHA-256 byte verification
#
# Usage:
#   ./scripts/smoke_test.sh
#   BASE_URL="https://localhost" ./scripts/smoke_test.sh
# ==============================================================================

set -euo pipefail

BASE_URL="${BASE_URL:-https://localhost}"
HTTP_URL="${BASE_URL/https:\/\//http:\/\/}"
CURL_OPTS=(-sS -k) # -k allows Caddy's local internal CA certificate

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

TEST_FILE="$TMP_DIR/smoke_test_$(date +%s).txt"
DOWNLOAD_FILE="$TMP_DIR/downloaded.txt"

echo "Cloud File Exchange smoke test payload — $(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$TEST_FILE"
ORIG_SHA256="$(shasum -a 256 "$TEST_FILE" | awk '{print $1}')"

echo "==> [1/4] Checking HTTP -> HTTPS redirect on $HTTP_URL ..."
HTTP_STATUS="$(curl -sS -o /dev/null -w "%{http_code}" "$HTTP_URL" || true)"
if [[ "$HTTP_STATUS" == "301" || "$HTTP_STATUS" == "302" || "$HTTP_STATUS" == "307" || "$HTTP_STATUS" == "308" ]]; then
    echo "    OK: Plain HTTP returned redirect status $HTTP_STATUS"
else
    echo "    FAIL: Expected HTTP redirect (301/302/307/308), got $HTTP_STATUS"
    exit 1
fi

echo "==> [2/4] Uploading test file to $BASE_URL/api/files ..."
UPLOAD_RESP="$(curl "${CURL_OPTS[@]}" -X POST "$BASE_URL/api/files" -F "file=@$TEST_FILE")"
FILE_ID="$(python3 -c 'import sys, json; print(json.loads(sys.argv[1])["id"])' "$UPLOAD_RESP")"
echo "    OK: Uploaded file ID = $FILE_ID"

echo "==> [3/4] Listing files from $BASE_URL/api/files ..."
LIST_RESP="$(curl "${CURL_OPTS[@]}" "$BASE_URL/api/files")"
python3 -c '
import sys, json
data = json.loads(sys.argv[1])
file_id = sys.argv[2]
ids = [item["id"] for item in data.get("items", [])]
assert file_id in ids, f"Uploaded file {file_id} not found in list!"
' "$LIST_RESP" "$FILE_ID"
echo "    OK: File $FILE_ID appears in GET /api/files"

echo "==> [4/4] Downloading $BASE_URL/api/files/$FILE_ID/download and verifying SHA-256 ..."
curl "${CURL_OPTS[@]}" "$BASE_URL/api/files/$FILE_ID/download" -o "$DOWNLOAD_FILE"
DOWN_SHA256="$(shasum -a 256 "$DOWNLOAD_FILE" | awk '{print $1}')"

if [[ "$ORIG_SHA256" == "$DOWN_SHA256" ]]; then
    echo "    OK: SHA-256 matches ($ORIG_SHA256)"
else
    echo "    FAIL: SHA-256 mismatch! Original=$ORIG_SHA256 Downloaded=$DOWN_SHA256"
    exit 1
fi

echo "✅ Smoke test passed end-to-end!"
