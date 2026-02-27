#!/bin/bash

set -e
echo "=== Starting Globus Transfer Script ==="

# Load environment variables
source .env
SRC_ENDPOINT=32e6b738-a0b0-47f8-b475-26bf1c5ebf19  # Mind2Web globus endpoint

SRC_PATH="${SRC_ENDPOINT}:/data/raw_dump/task/"
DST_PATH="${LOCAL_ENDPOINT}:${GLOBUS_LOCAL_PATH}/task/"

echo "--- Transferring Mind2Web data ---"
echo "  SRC: $SRC_PATH"
echo "  DST: $DST_PATH"

globus transfer --recursive "$SRC_PATH" "$DST_PATH"
echo ""

echo "=== Transfer complete ==="

# To see tasks run today
# globus task list --filter-requested-after 2025-11-04T00:00:00 

# To cancel all tasks
# globus task cancel --all 