#!/bin/bash
gunicorn --bind 0.0.0.0:${PORT:-5000} app_simple:app
