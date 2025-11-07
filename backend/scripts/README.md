# Backend Utility Scripts

This directory contains utility scripts for development and maintenance of the Construction Spec Assistant backend.

## Available Scripts

### cleanup_mongodb.py

A utility script to clean up MongoDB collections for testing purposes.

#### Purpose

This script connects to the MongoDB database and deletes all documents from the following collections:
- `chunks` - Document chunks for vector storage
- `document_comparison_results` - Comparison analysis results
- `documents` - Main document records
- `facts` - Extracted facts from documents
- `sections` - Document sections

#### Usage

**From the project root directory:**

```bash
# Interactive mode (with confirmation prompt)
uv run python backend/scripts/cleanup_mongodb.py

# Non-interactive mode (skip confirmation)
uv run python backend/scripts/cleanup_mongodb.py --yes
```

**From the backend directory:**

```bash
# Interactive mode
cd backend
uv run python scripts/cleanup_mongodb.py

# Non-interactive mode
uv run python scripts/cleanup_mongodb.py --yes
```

#### Features

- **Connection Validation**: Verifies MongoDB connection before proceeding
- **Statistics Display**: Shows current document counts for all collections
- **Confirmation Prompt**: Requires user confirmation before deletion (unless `--yes` flag is used)
- **Progress Reporting**: Displays detailed information about the cleanup process
- **Error Handling**: Gracefully handles connection errors and missing collections
- **Summary Report**: Shows total documents deleted and verifies cleanup completion

#### Example Output

```
============================================================
MongoDB Cleanup Utility
Construction Spec Assistant - Development Tool
============================================================
2025-11-07 08:49:02 - __main__ - INFO - Connecting to MongoDB at mongodb://localhost:27017
2025-11-07 08:49:02 - __main__ - INFO - Successfully connected to MongoDB

Database: construction_spec_assistant
============================================================

Current collection statistics:
  - chunks: 150 documents
  - document_comparison_results: 5 documents
  - documents: 10 documents
  - facts: 200 documents
  - sections: 50 documents

⚠️  WARNING: This will permanently delete all data from the above collections!
⚠️  This action cannot be undone!

Are you sure you want to proceed? (yes/no): yes

Starting cleanup...
============================================================
✓ Cleaned collection 'chunks': 150 documents deleted
✓ Cleaned collection 'document_comparison_results': 5 documents deleted
✓ Cleaned collection 'documents': 10 documents deleted
✓ Cleaned collection 'facts': 200 documents deleted
✓ Cleaned collection 'sections': 50 documents deleted

============================================================
Cleanup Summary:
  Total documents deleted: 415
============================================================

✓ Cleanup completed successfully. All collections are now empty.
```

#### Prerequisites

- MongoDB must be running (use `docker-compose up -d mongodb` to start)
- The script uses the MongoDB connection settings from the application configuration (`.env` file)

#### Safety Features

- **Confirmation Required**: By default, the script requires explicit user confirmation
- **Development Only**: This script is intended for development/testing environments only
- **Clear Warnings**: Displays prominent warnings before performing any deletions
- **Detailed Logging**: Provides comprehensive logging of all operations

#### Troubleshooting

**Connection Error:**
```
✗ Connection error: Could not connect to MongoDB: ...
Please ensure MongoDB is running and accessible.
You can start MongoDB using: docker-compose up -d mongodb
```

**Solution:** Start MongoDB using Docker Compose:
```bash
cd backend
docker-compose up -d mongodb
```

**Module Not Found Error:**
```
ModuleNotFoundError: No module named 'motor'
```

**Solution:** Make sure to use `uv run` to execute the script with the proper Python environment.

## Adding New Scripts

When adding new utility scripts to this directory:

1. Follow the existing code structure and conventions
2. Use the application's logging utilities (`app.utils.logging`)
3. Import configuration from `app.config.settings`
4. Include proper docstrings and type hints
5. Add error handling for common failure scenarios
6. Update this README with documentation for the new script
7. Make the script executable: `chmod +x scripts/your_script.py`
8. Add a shebang line: `#!/usr/bin/env python3`

## Best Practices

- Always test scripts in a development environment first
- Use logging instead of print statements
- Provide clear user feedback and progress indicators
- Include confirmation prompts for destructive operations
- Handle errors gracefully with meaningful error messages
- Document all command-line arguments and options

