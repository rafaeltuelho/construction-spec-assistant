"""
Test script for manufacturer extraction enhancement.

This script tests the new manufacturer extraction logic with the example document.
"""

import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.models.fact import Fact
from app.services.fact_extraction import extract_manufacturer_mappings


class SimpleChunk:
    """Simple chunk representation for testing."""

    def __init__(self, section_id: str, header_path: list[str], text: str):
        self.section_id = section_id
        self.header_path = header_path
        self.content = text


def load_facts_from_jsonl(file_path: str) -> list[Fact]:
    """Load facts from JSONL file."""
    facts = []
    with open(file_path, "r") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                facts.append(Fact(**data))
    return facts


def load_chunks_from_jsonl(file_path: str) -> list[SimpleChunk]:
    """Load document chunks from JSONL file."""
    chunks = []
    with open(file_path, "r") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                chunks.append(
                    SimpleChunk(
                        section_id=data["section_id"],
                        header_path=data["header_path"],
                        text=data["text"],
                    )
                )
    return chunks


def main():
    """Test manufacturer extraction with example document."""
    print("=" * 80)
    print("Testing Manufacturer Extraction Enhancement")
    print("=" * 80)
    print()

    # Load test data
    facts_file = "experimental_data/parsed/Spec 14 24 00 - Hydraulic Elevators_redacted.facts.jsonl"
    chunks_file = "experimental_data/parsed/Spec 14 24 00 - Hydraulic Elevators_redacted_20251021_172135.section_chunks.jsonl"

    print(f"Loading facts from: {facts_file}")
    facts = load_facts_from_jsonl(facts_file)
    print(f"✓ Loaded {len(facts)} facts")
    print()

    print(f"Loading chunks from: {chunks_file}")
    chunks = load_chunks_from_jsonl(chunks_file)
    print(f"✓ Loaded {len(chunks)} chunks")
    print()

    # Extract manufacturer mappings
    print("Extracting manufacturer mappings...")
    print("-" * 80)
    manufacturer_mappings = extract_manufacturer_mappings(facts, chunks)
    print("-" * 80)
    print()

    # Display results
    print("Results:")
    print("=" * 80)
    if manufacturer_mappings:
        for entity_type, manufacturers in manufacturer_mappings.items():
            print(f"\nEntity Type: {entity_type}")
            print(f"Manufacturers:")
            for manufacturer in manufacturers:
                print(f"  - {manufacturer}")
    else:
        print("No manufacturer mappings found")
    print()

    # Verify expected result
    print("Verification:")
    print("=" * 80)
    expected_manufacturer = "ThyssenKrupp Elevator"
    expected_entity_type = "elevator"

    if expected_entity_type in manufacturer_mappings:
        manufacturers = manufacturer_mappings[expected_entity_type]
        if expected_manufacturer in manufacturers:
            print(
                f"✓ SUCCESS: Found expected manufacturer '{expected_manufacturer}' for entity type '{expected_entity_type}'"
            )
        else:
            print(f"✗ FAILURE: Expected manufacturer '{expected_manufacturer}' not found")
            print(f"  Found: {manufacturers}")
    else:
        print(f"✗ FAILURE: Entity type '{expected_entity_type}' not found in mappings")
        print(f"  Found entity types: {list(manufacturer_mappings.keys())}")
    print()


if __name__ == "__main__":
    main()
