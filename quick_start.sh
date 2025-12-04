#!/bin/bash

# CrawlerWhipAI Quick Start Script

echo "🚀 CrawlerWhipAI Quick Start Setup"
echo "===================================="
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Install package
echo "📥 Installing CrawlerWhipAI..."
pip install -e .

# Install browser binaries
echo "🌐 Installing browser binaries..."
playwright install chromium

# Run basic test
echo ""
echo "🧪 Running basic test..."
python3 -c "
import asyncio
from crawlerWhipAI import AsyncWebCrawler

async def test():
    print('Testing AsyncWebCrawler import...')
    crawler = AsyncWebCrawler()
    print('✓ AsyncWebCrawler imported successfully!')

try:
    asyncio.run(test())
except Exception as e:
    print(f'Error: {e}')
" && echo "✓ Basic test passed" || echo "✗ Basic test failed"

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Activate environment: source venv/bin/activate"
echo "2. Run examples: python examples/basic_crawl.py"
echo "3. Read docs: cat GETTING_STARTED.md"
echo "4. Run tests: pytest tests/ -v"
echo ""
echo "Happy crawling! 🕷️"
