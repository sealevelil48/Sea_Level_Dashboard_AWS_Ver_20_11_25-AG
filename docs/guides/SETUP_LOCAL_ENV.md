# Local Development Environment Setup

**⚠️ CRITICAL**: Never commit `.env` files or any files containing secrets to git.

## Quick Start

### 1. Backend Environment Setup

```bash
# Copy the example environment file
cp backend/.env.example backend/.env

# Edit the .env file with YOUR local values
# Update the database password, API keys, etc.
nano backend/.env
```

**Key values to update in .env**:
- `DATABASE_URL`: Your local PostgreSQL connection
- `REDIS_URL`: Your local Redis (or use defaults if using Docker)
- `Govmap_API_KEY`: Get from team or AWS Secrets Manager

### 2. Using Docker Compose (Recommended)

If you want to run PostgreSQL and Redis in Docker:

```bash
# Set your database password as an environment variable
export DB_PASSWORD="your_development_password"

# Start all services (PostgreSQL, Redis, Backend, Frontend)
docker-compose up -d

# Verify services are running
docker-compose ps
```

This starts:
- PostgreSQL on `localhost:5432`
- Redis on `localhost:6379`
- Backend API on `localhost:8000`
- Frontend on `localhost:3000`

### 3. Backend Server (Local Development)

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables for local development
export DATABASE_URL="postgresql://sealevel_user:dev_password@localhost:5432/sealevel_dev"
export SECRET_KEY="dev-secret-key"

# Run the FastAPI server
python local_server.py
# Server runs on http://localhost:30886
```

### 4. Frontend (React Development)

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm start
# Frontend runs on http://localhost:3000
```

## Production Secrets (AWS)

**DO NOT store production secrets in `.env` files.**

For AWS production deployment:
- Database credentials are loaded from **AWS Secrets Manager**
- API keys are loaded from **AWS Secrets Manager**
- Lambda functions fetch secrets at runtime

See `SOLO-DEPLOYMENT-PLAN.md` for AWS Secrets Manager setup.

## Git Safety

Before committing, verify that `.env` files are NOT staged:

```bash
# Check status
git status

# Should NOT show any .env files
# If it does: git reset backend/.env

# Verify .gitignore protection
cat .gitignore | grep -E "\.env|secrets"
```

## Troubleshooting

### Database connection error

**Error**: `could not connect to server: Connection refused`

**Solution**:
```bash
# If using Docker
docker-compose up -d postgres

# If using local PostgreSQL
psql -U sealevel_user -d sealevel_dev
```

### `.env` file not found

**Solution**:
```bash
cp backend/.env.example backend/.env
# Edit with your values
```

### Redis connection error

**Solution**:
```bash
# Start Redis in Docker
docker-compose up -d redis

# OR if using local Redis
redis-cli ping  # Should return PONG
```

## File Structure After Setup

```
Sea_Level_Dashboard_AWS_Ver_20_11_25-AG/
├── backend/
│   ├── .env              ← Created from .env.example (NOT in git)
│   ├── .env.example      ← Safe template (IN git)
│   ├── venv/             ← Virtual environment
│   └── local_server.py   ← Development server
├── frontend/
│   ├── node_modules/     ← Dependencies (not in git)
│   └── src/
├── docker-compose.yml    ← Development stack
└── SETUP_LOCAL_ENV.md    ← This file
```

## Questions?

- See `CLAUDE.md` for architecture documentation
- See `SOLO-DEPLOYMENT-PLAN.md` for AWS production setup
- See `API_DOCUMENTATION.md` for API endpoints
