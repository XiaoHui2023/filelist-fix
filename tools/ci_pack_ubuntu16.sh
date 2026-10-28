#!/usr/bin/env bash
# Run only inside the Ubuntu 16.04 CI container; both native wrapping stages stay here.
set -euo pipefail
cd /work
export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::Retries=3 update
apt-get install -o Acquire::Retries=3 -y --no-install-recommends ca-certificates wget curl bzip2 binutils patchelf build-essential musl-tools zlib1g-dev liblzma-dev pkg-config
MINICONDA=Miniconda3-py310_23.5.2-0-Linux-x86_64.sh
wget --tries=3 --timeout=30 -O "/tmp/$MINICONDA" "https://repo.anaconda.com/miniconda/$MINICONDA"
bash "/tmp/$MINICONDA" -b -p /opt/conda
export PATH="/opt/conda/bin:$PATH"
python -m venv .venv
bash tools/pack.sh

.venv/bin/python -m pip install pytest==8.3.5
.venv/bin/python -m pytest -q
