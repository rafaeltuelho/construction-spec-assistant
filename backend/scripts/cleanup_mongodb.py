#!/usr/bin/env python3
"""
MongoDB Cleanup Utility Script

This script cleans up MongoDB collections for testing purposes.
It connects to the MongoDB database using the application configuration
and deletes all documents from specified collections.

Usage:
    python scripts/cleanup_mongodb.py [--yes]

Options:
    --yes    Skip confirmation prompt and proceed with cleanup

WARNING: This script is for development/testing purposes only.
         It will permanently delete all data from the specified collections.
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.utils.logging import get_logger, setup_logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

# Setup logging
setup_logging(level=settings.log_level, log_format="text")
logger = get_logger(__name__)

# Collections to clean up
COLLECTIONS_TO_CLEAN = [
    "chunks",
    "document_comparison_results",
    "documents",
    "facts",
    "sections",
]


async def connect_to_mongodb() -> AsyncIOMotorClient:
    """
    Connect to MongoDB using application configuration.

    Returns:
        MongoDB client instance

    Raises:
        ConnectionError: If connection fails
    """
    try:
        logger.info(f"Connecting to MongoDB at {settings.mongodb_url}")
        client = AsyncIOMotorClient(
            settings.mongodb_url,
            serverSelectionTimeoutMS=5000,
        )

        # Test connection
        await client.admin.command("ping")
        logger.info("Successfully connected to MongoDB")

        return client

    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise ConnectionError(f"Could not connect to MongoDB: {e}") from e


async def get_collection_stats(db: AsyncIOMotorDatabase) -> Dict[str, int]:
    """
    Get document counts for all collections to be cleaned.

    Args:
        db: MongoDB database instance

    Returns:
        Dictionary mapping collection names to document counts
    """
    stats = {}

    for collection_name in COLLECTIONS_TO_CLEAN:
        try:
            count = await db[collection_name].count_documents({})
            stats[collection_name] = count
        except Exception as e:
            logger.warning(f"Could not get stats for collection '{collection_name}': {e}")
            stats[collection_name] = 0

    return stats


async def cleanup_collection(db: AsyncIOMotorDatabase, collection_name: str) -> int:
    """
    Delete all documents from a collection.

    Args:
        db: MongoDB database instance
        collection_name: Name of the collection to clean

    Returns:
        Number of documents deleted

    Raises:
        Exception: If cleanup fails
    """
    try:
        result = await db[collection_name].delete_many({})
        deleted_count = result.deleted_count
        logger.info(f"✓ Cleaned collection '{collection_name}': {deleted_count} documents deleted")
        return deleted_count

    except Exception as e:
        logger.error(f"✗ Failed to clean collection '{collection_name}': {e}")
        raise


async def cleanup_mongodb(skip_confirmation: bool = False) -> None:
    """
    Main cleanup function.

    Args:
        skip_confirmation: If True, skip the confirmation prompt
    """
    client = None

    try:
        # Connect to MongoDB
        client = await connect_to_mongodb()
        db = client[settings.mongodb_database]

        # Get current stats
        logger.info(f"\nDatabase: {settings.mongodb_database}")
        logger.info("=" * 60)

        stats_before = await get_collection_stats(db)

        # Display current state
        logger.info("\nCurrent collection statistics:")
        total_docs = 0
        for collection_name, count in stats_before.items():
            logger.info(f"  - {collection_name}: {count} documents")
            total_docs += count

        if total_docs == 0:
            logger.info("\n✓ All collections are already empty. Nothing to clean.")
            return

        # Confirmation prompt
        if not skip_confirmation:
            logger.warning(
                "\n⚠️  WARNING: This will permanently delete all data from the above collections!"
            )
            logger.warning("⚠️  This action cannot be undone!")

            response = input("\nAre you sure you want to proceed? (yes/no): ").strip().lower()

            if response not in ["yes", "y"]:
                logger.info("Cleanup cancelled by user.")
                return

        # Perform cleanup
        logger.info("\nStarting cleanup...")
        logger.info("=" * 60)

        total_deleted = 0
        for collection_name in COLLECTIONS_TO_CLEAN:
            try:
                deleted = await cleanup_collection(db, collection_name)
                total_deleted += deleted
            except Exception as e:
                logger.error(f"Error cleaning {collection_name}: {e}")
                # Continue with other collections even if one fails

        # Display summary
        logger.info("\n" + "=" * 60)
        logger.info("Cleanup Summary:")
        logger.info(f"  Total documents deleted: {total_deleted}")
        logger.info("=" * 60)

        # Verify cleanup
        stats_after = await get_collection_stats(db)
        remaining_docs = sum(stats_after.values())

        if remaining_docs == 0:
            logger.info("\n✓ Cleanup completed successfully. All collections are now empty.")
        else:
            logger.warning(f"\n⚠️  Warning: {remaining_docs} documents still remain in collections.")
            logger.info("\nRemaining documents:")
            for collection_name, count in stats_after.items():
                if count > 0:
                    logger.info(f"  - {collection_name}: {count} documents")

    except ConnectionError as e:
        logger.error(f"\n✗ Connection error: {e}")
        logger.error("Please ensure MongoDB is running and accessible.")
        logger.error("You can start MongoDB using: docker-compose up -d mongodb")
        sys.exit(1)

    except Exception as e:
        logger.error(f"\n✗ Unexpected error during cleanup: {e}")
        sys.exit(1)

    finally:
        if client:
            client.close()
            logger.debug("MongoDB connection closed")


def main():
    """Main entry point."""
    # Parse command line arguments
    skip_confirmation = "--yes" in sys.argv or "-y" in sys.argv

    # Display header
    print("\n" + "=" * 60)
    print("MongoDB Cleanup Utility")
    print("Construction Spec Assistant - Development Tool")
    print("=" * 60)

    # Run cleanup
    try:
        asyncio.run(cleanup_mongodb(skip_confirmation=skip_confirmation))
    except KeyboardInterrupt:
        logger.info("\n\nCleanup interrupted by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
