#!/bin/bash
# ============================================================
# OMNI2 Startup Script (Linux/Mac)
# ============================================================

echo "🚀 Starting OMNI2 Bridge..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp .env.example .env
    echo "✅ Created .env file. Please edit it with your credentials."
    echo ""
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Build and start services
echo "🔨 Building Docker images..."
docker-compose build

echo ""
echo "🚀 Starting services..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 5

# Check health
echo ""
echo "🏥 Checking health..."
curl -s http://localhost:8000/health | python -m json.tool || echo "Service not ready yet..."

echo ""
echo "✅ OMNI2 is running!"
echo ""
echo "📚 Access points:"
echo "   - API:    http://localhost:8000"
echo "   - Docs:   http://localhost:8000/docs"
echo "   - Health: http://localhost:8000/health"
echo ""
echo "📝 View logs:"
echo "   docker-compose logs -f omni2"
echo ""
echo "🛑 Stop services:"
echo "   docker-compose down"
