#!/bin/sh
set -e

# seed the database here
python -m experiments.sqlalchemy_1_4_vs_2_0.seed

exec "$@"