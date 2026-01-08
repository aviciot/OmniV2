# OMNI2 Database Management Scripts

This directory contains PowerShell scripts for managing the OMNI2 database.

## Scripts

### `db-reset.ps1`
Completely drops and recreates the database. **⚠️ WARNING: Deletes all data!**

**Usage:**
```powershell
# Interactive mode (prompts for confirmation)
.\scripts\db-reset.ps1

# Force mode (no confirmation)
.\scripts\db-reset.ps1 -Force

# Skip seed data
.\scripts\db-reset.ps1 -NoSeed
```

**What it does:**
1. Drops the `omni` database
2. Creates a new empty `omni` database
3. Runs `init.sql` (creates all tables, views, indexes)
4. Runs `seed.sql` (populates initial users and MCP servers)

### `db-init.ps1`
Runs init.sql and seed.sql on an existing database.

**Usage:**
```powershell
# Full initialization
.\scripts\db-init.ps1

# Skip seed data
.\scripts\db-init.ps1 -NoSeed
```

**What it does:**
1. Runs `init.sql` (creates tables if not exists)
2. Runs `seed.sql` (upserts users and MCP servers)

### `import_users_yaml.py`
Imports `config/users.yaml` into the database (roles, teams, users, and permissions).

**Usage:**
```powershell
python scripts/import_users_yaml.py
```

**What it does:**
1. Upserts roles + teams from `users.yaml`
2. Upserts user settings (default user, provisioning, session, audit)
3. Upserts users, team memberships, and per-MCP permissions

## Initial Setup

### Fresh Docker Container
When you spin up a fresh Docker container, the database will automatically initialize:

```powershell
docker-compose down -v  # Remove old volumes
docker-compose up -d    # Start with fresh database
```

The `init.sql` and `seed.sql` scripts are mounted in `/docker-entrypoint-initdb.d/` and run automatically on first start.

### Manual Reset (while containers are running)
If you need to reset the database while containers are running:

```powershell
.\scripts\db-reset.ps1 -Force
docker-compose restart omni2  # Restart application
```

## Seed Data

The `seed.sql` script creates the following users:

| Email | Name | Role | Super Admin |
|-------|------|------|-------------|
| avicoiot@gmail.com | Avi Cohen | admin | Yes |
| avi.cohen@shift4.com | Avi Cohen | admin | Yes |
| alonab@shift4.com | Alon AB | developer | No |
| dba1@shift4.com | DBA User | dba | No |

And registers these MCP servers:
- `database_mcp` (enabled)
- `github_mcp` (enabled)
- `filesystem_mcp` (disabled)
- `smoketest_mcp` (disabled)

## Troubleshooting

### Scripts don't run
Make sure you're in the `omni2` directory:
```powershell
cd "c:\Users\acohen.SHIFT4CORP\Desktop\PythonProjects\MCP Performance\omni2"
```

### Container not found
Make sure PostgreSQL container is running:
```powershell
docker ps | Select-String "omni2-postgres"
```

### Permission denied
Run PowerShell as Administrator or change execution policy:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Migration Files

- `migrations/init.sql` - Complete database schema (consolidated from 001 + 002)
- `migrations/003_roles_teams_user_settings.sql` - Adds roles, teams, user settings, and per-user MCP permissions
- `migrations/seed.sql` - Initial data (users, MCP servers)
- `migrations/archive/` - Old migration files (for reference)
