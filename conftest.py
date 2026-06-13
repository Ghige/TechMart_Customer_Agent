"""
pytest configuration — adds the project root to sys.path so that
`import backend.*` works regardless of where pytest is invoked from.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
