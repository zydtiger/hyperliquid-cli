#!/bin/bash
# Coverage Generation Script
# This script generates test coverage reports and badges

set -e

echo "🧪 Running tests with coverage..."
uv run pytest --cov=src --cov-report=html --cov-report=term-missing

echo "📊 Generating JSON coverage report..."
uv run coverage json

echo "🏷️  Generating coverage badge..."
uv run python scripts/generate_coverage_badge.py

echo "🧹 Cleaning up temporary coverage files..."
rm .coverage
rm coverage.json

echo "✅ Coverage generation complete!"
echo "📈 HTML report: htmlcov/index.html"
echo "🏷️  Coverage badge: badges/coverage.svg"