"""
Script to inspect MongoDB data for manufacturer extraction debugging.

This script connects to MongoDB and inspects the actual structure of facts,
sections, and chunks to understand why manufacturer extraction is not working.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
from app.utils.logging import setup_logging, get_logger

setup_logging(level="INFO", log_format="text")
logger = get_logger(__name__)


async def inspect_latest_document():
    """Inspect the most recently processed document."""
    client = None
    
    try:
        # Connect to MongoDB
        logger.info(f"Connecting to MongoDB at {settings.mongodb_url}")
        client = AsyncIOMotorClient(settings.mongodb_url)
        db = client[settings.mongodb_database]
        
        # Test connection
        await client.admin.command("ping")
        logger.info("✓ Connected to MongoDB")
        
        # Get the most recent document with facts
        logger.info("\n" + "=" * 80)
        logger.info("Finding most recent document with facts...")
        logger.info("=" * 80)

        # First, check if there are any facts at all
        total_facts = await db.facts.count_documents({})
        logger.info(f"Total facts in database: {total_facts}")

        if total_facts == 0:
            logger.error("No facts found in database!")
            logger.info("\nChecking all documents...")
            all_docs = await db.documents.find({}).to_list(length=None)
            logger.info(f"Total documents in database: {len(all_docs)}")
            if all_docs:
                logger.info("\nRecent documents:")
                for doc in all_docs[:5]:
                    logger.info(f"  - {doc['_id']}: {doc.get('filename', 'Unknown')} (created: {doc.get('created_at')})")
            return

        # Find a document with facts
        sample_fact = await db.facts.find_one({})
        logger.info(f"\nSample fact keys: {list(sample_fact.keys())}")

        # Try different field names
        doc_id = sample_fact.get("doc_id") or sample_fact.get("document_id") or sample_fact.get("context", {}).get("doc_id")

        if not doc_id:
            logger.error(f"Could not find doc_id in fact! Sample fact: {sample_fact}")
            return

        # Count facts for this document (try different field names)
        fact_count = await db.facts.count_documents({"context.doc_id": doc_id})
        if fact_count == 0:
            fact_count = await db.facts.count_documents({"doc_id": doc_id})
        if fact_count == 0:
            fact_count = await db.facts.count_documents({"document_id": doc_id})

        # Get document details
        document = await db.documents.find_one({"_id": doc_id})

        if not document:
            logger.warning(f"Document {doc_id} not found in documents collection!")
            logger.info(f"But found {fact_count} facts with doc_id={doc_id}")
        else:
            doc_name = document.get("filename", "Unknown")
            logger.info(f"\nDocument ID: {doc_id}")
            logger.info(f"Filename: {doc_name}")
            logger.info(f"Created: {document.get('created_at')}")

        logger.info(f"Facts count: {fact_count}")
        
        # Get facts for this document
        logger.info("\n" + "=" * 80)
        logger.info("Analyzing facts...")
        logger.info("=" * 80)

        # Try different field names for querying
        facts_cursor = db.facts.find({"context.doc_id": doc_id})
        facts = await facts_cursor.to_list(length=None)

        if not facts:
            facts_cursor = db.facts.find({"doc_id": doc_id})
            facts = await facts_cursor.to_list(length=None)

        if not facts:
            facts_cursor = db.facts.find({"document_id": doc_id})
            facts = await facts_cursor.to_list(length=None)
        
        logger.info(f"\nTotal facts: {len(facts)}")
        
        if not facts:
            logger.warning("No facts found for this document!")
            return
        
        # Analyze header paths in facts
        logger.info("\n" + "=" * 80)
        logger.info("Sample header paths from facts (first 20 unique):")
        logger.info("=" * 80)
        
        header_paths = set()
        manufacturer_facts = []
        
        for fact in facts:
            context = fact.get("context", {})
            header_path = context.get("header_path", [])
            
            if header_path:
                header_path_str = " > ".join(header_path)
                header_paths.add(header_path_str)
                
                # Check if this is a manufacturer section
                if "PART 2" in header_path_str.upper() and "MANUFACTURERS" in header_path_str.upper():
                    manufacturer_facts.append(fact)
        
        # Display sample header paths
        for i, hp in enumerate(sorted(header_paths)[:20], 1):
            logger.info(f"{i:2d}. {hp}")
        
        if len(header_paths) > 20:
            logger.info(f"... and {len(header_paths) - 20} more unique header paths")
        
        # Check for manufacturer sections
        logger.info("\n" + "=" * 80)
        logger.info("Checking for manufacturer sections...")
        logger.info("=" * 80)
        
        logger.info(f"\nFacts with 'PART 2' AND 'MANUFACTURERS' in header_path: {len(manufacturer_facts)}")
        
        if manufacturer_facts:
            logger.info("\n✓ Found manufacturer facts!")
            logger.info("\nSample manufacturer facts:")
            for i, fact in enumerate(manufacturer_facts[:5], 1):
                context = fact.get("context", {})
                header_path = " > ".join(context.get("header_path", []))
                entity = fact.get("entity", {}).get("raw", "N/A")
                attribute = fact.get("attribute", {}).get("raw", "N/A")
                value = fact.get("value", {}).get("raw", "N/A")

                logger.info(f"\n{i}. Header Path: {header_path}")
                logger.info(f"   Entity: {entity}")
                logger.info(f"   Attribute: {attribute}")
                logger.info(f"   Value: {value[:100]}...")
        else:
            logger.warning("\n✗ No manufacturer facts found!")
            logger.warning("Searching for sections containing 'MANUFACTURER' (singular)...")

            manufacturer_singular = []
            for hp in sorted(header_paths):
                if "MANUFACTURER" in hp.upper():
                    manufacturer_singular.append(hp)

            if manufacturer_singular:
                logger.info(f"\nFound {len(manufacturer_singular)} sections with 'MANUFACTURER':")
                for hp in manufacturer_singular[:10]:
                    logger.info(f"  - {hp}")
            else:
                logger.warning("No sections with 'MANUFACTURER' found at all!")

        # Analyze entity type distribution
        logger.info("\n" + "=" * 80)
        logger.info("Analyzing entity type distribution...")
        logger.info("=" * 80)

        entity_type_counts = {}
        entity_with_manufacturer = {}

        for fact in facts:
            entity = fact.get("entity", {})
            entity_type = entity.get("type", "unknown")
            manufacturer = entity.get("manufacturer")

            entity_type_counts[entity_type] = entity_type_counts.get(entity_type, 0) + 1

            if manufacturer:
                entity_with_manufacturer[entity_type] = entity_with_manufacturer.get(entity_type, 0) + 1

        logger.info(f"\nEntity type distribution (top 10):")
        sorted_types = sorted(entity_type_counts.items(), key=lambda x: x[1], reverse=True)
        for i, (entity_type, count) in enumerate(sorted_types[:10], 1):
            with_mfr = entity_with_manufacturer.get(entity_type, 0)
            entity_type_str = str(entity_type) if entity_type else "None"
            logger.info(f"{i:2d}. {entity_type_str:20s}: {count:3d} facts ({with_mfr:3d} with manufacturer)")

        if len(sorted_types) > 10:
            logger.info(f"... and {len(sorted_types) - 10} more entity types")

        total_with_manufacturer = sum(entity_with_manufacturer.values())
        logger.info(f"\nTotal facts with manufacturer: {total_with_manufacturer}/{len(facts)}")
        
        # Get sections for this document
        logger.info("\n" + "=" * 80)
        logger.info("Analyzing sections...")
        logger.info("=" * 80)
        
        sections_cursor = db.sections.find({"document_id": doc_id})
        sections = await sections_cursor.to_list(length=None)
        
        logger.info(f"\nTotal sections: {len(sections)}")
        
        if sections:
            logger.info("\nSample section header paths (first 20):")
            for i, section in enumerate(sections[:20], 1):
                header_path = section.get("header_path", [])
                header_path_str = " > ".join(header_path)
                logger.info(f"{i:2d}. {header_path_str}")
            
            # Check for manufacturer sections in sections
            manufacturer_sections = []
            for section in sections:
                header_path = section.get("header_path", [])
                header_path_str = " > ".join(header_path)
                if "PART 2" in header_path_str.upper() and "MANUFACTURERS" in header_path_str.upper():
                    manufacturer_sections.append(section)
            
            logger.info(f"\nSections with 'PART 2' AND 'MANUFACTURERS': {len(manufacturer_sections)}")
            
            if manufacturer_sections:
                logger.info("\n✓ Found manufacturer sections!")
                for i, section in enumerate(manufacturer_sections[:5], 1):
                    header_path = " > ".join(section.get("header_path", []))
                    title = section.get("title", "N/A")
                    content_preview = section.get("content", "")[:200]
                    logger.info(f"\n{i}. Header Path: {header_path}")
                    logger.info(f"   Title: {title}")
                    logger.info(f"   Content Preview: {content_preview}...")
        
        # Get chunks for this document
        logger.info("\n" + "=" * 80)
        logger.info("Analyzing chunks...")
        logger.info("=" * 80)
        
        chunks_cursor = db.chunks.find({"document_id": doc_id})
        chunks = await chunks_cursor.to_list(length=None)
        
        logger.info(f"\nTotal chunks: {len(chunks)}")
        
        if chunks:
            logger.info("\nSample chunk section titles (first 20):")
            for i, chunk in enumerate(chunks[:20], 1):
                section_title = chunk.get("section_title", "N/A")
                logger.info(f"{i:2d}. {section_title}")
        
        logger.info("\n" + "=" * 80)
        logger.info("Inspection complete!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Error during inspection: {e}", exc_info=True)
    
    finally:
        if client:
            client.close()
            logger.info("\nMongoDB connection closed")


if __name__ == "__main__":
    asyncio.run(inspect_latest_document())

