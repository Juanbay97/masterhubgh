#!/bin/bash
set -euo pipefail

source /runtime-common.sh

initialize_bench_if_needed
configure_bench_runtime
sync_site_runtime_mode 1

echo "==> Arrancando HubGH en modo DESARROLLO (bench start)..."
exec bench start
