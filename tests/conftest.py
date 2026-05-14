"""Shared pytest configuration."""
import os
import sys

# Ensure repo root doesn't shadow pip packages
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root in sys.path:
    sys.path.remove(_repo_root)
