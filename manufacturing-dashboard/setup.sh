#!/usr/bin/env bash
set -e

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

mkdir -p instance
python db_init.py

echo "Setup complete. Use ./run.sh to start the server."
