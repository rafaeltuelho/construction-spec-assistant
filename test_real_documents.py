#!/usr/bin/env python3
"""
Test sectionization with real CSI specification documents.

This script compares hierarchical vs notebook-style sectionization on actual documents.
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from app.core.sectionizer import sectionize_markdown, flatten_sections, count_sections


def print_section_tree(sections, indent=0):
    """Print hierarchical section tree."""
    for section in sections:
        prefix = "  " * indent
        print(f"{prefix}- {section.title} (level {section.level})")
        print(f"{prefix}  ID: {section.section_id}")
        print(f"{prefix}  Path: {' > '.join(section.header_path)}")
        print(f"{prefix}  Content: {len(section.content)} chars")
        if section.subsections:
            print_section_tree(section.subsections, indent + 1)


def print_flat_sections(sections):
    """Print flat section list."""
    for idx, section in enumerate(sections, 1):
        print(f"\n{idx}. {section.title}")
        print(f"   Level: {section.level}")
        print(f"   ID: {section.section_id}")
        print(f"   Path: {' > '.join(section.header_path)}")
        print(f"   Content: {len(section.content)} chars")
        if section.content:
            preview = section.content[:150].replace('\n', ' ')
            print(f"   Preview: {preview}...")


def analyze_sections(sections, mode_name):
    """Analyze and print statistics about sections."""
    print(f"\n{'=' * 80}")
    print(f"{mode_name} - Statistics")
    print(f"{'=' * 80}")
    
    # Count sections by level
    level_counts = {}
    total_content = 0
    sections_with_content = 0
    
    for section in sections:
        level_counts[section.level] = level_counts.get(section.level, 0) + 1
        total_content += len(section.content)
        if section.content.strip():
            sections_with_content += 1
    
    print(f"\nTotal sections: {len(sections)}")
    print(f"Sections with content: {sections_with_content}")
    print(f"Total content length: {total_content:,} chars")
    print(f"\nSections by level:")
    for level in sorted(level_counts.keys()):
        print(f"  Level {level}: {level_counts[level]} sections")
    
    # Show unique header paths
    print(f"\nUnique header paths (first 20):")
    for idx, section in enumerate(sections[:20], 1):
        path = ' > '.join(section.header_path)
        print(f"  {idx}. {path}")


def compare_modes(markdown_content, doc_name):
    """Compare hierarchical vs notebook-style sectionization."""
    print(f"\n{'#' * 80}")
    print(f"# Testing Document: {doc_name}")
    print(f"# Document size: {len(markdown_content):,} chars")
    print(f"{'#' * 80}\n")
    
    # Test hierarchical mode
    print("\n" + "=" * 80)
    print("HIERARCHICAL MODE (default)")
    print("=" * 80)
    hierarchical_sections = sectionize_markdown(markdown_content, use_notebook_logic=False)
    flat_hierarchical = flatten_sections(hierarchical_sections)
    
    print(f"\nTop-level sections: {len(hierarchical_sections)}")
    print(f"Total sections (flattened): {len(flat_hierarchical)}")
    
    print("\nHierarchical structure:")
    print_section_tree(hierarchical_sections)
    
    analyze_sections(flat_hierarchical, "Hierarchical Mode")
    
    # Test notebook-style mode
    print("\n\n" + "=" * 80)
    print("NOTEBOOK-STYLE MODE (flat with CSI-aware heuristics)")
    print("=" * 80)
    notebook_sections = sectionize_markdown(markdown_content, use_notebook_logic=True)
    
    print(f"\nTotal sections: {len(notebook_sections)}")
    print("\nFlat section list:")
    print_flat_sections(notebook_sections)
    
    analyze_sections(notebook_sections, "Notebook-Style Mode")
    
    # Comparison
    print("\n\n" + "=" * 80)
    print("COMPARISON")
    print("=" * 80)
    print(f"\nHierarchical mode: {len(flat_hierarchical)} sections (flattened)")
    print(f"Notebook-style mode: {len(notebook_sections)} sections")
    print(f"Difference: {abs(len(flat_hierarchical) - len(notebook_sections))} sections")
    
    # Compare PART sections
    hierarchical_parts = [s for s in flat_hierarchical if s.level == 1 and 'PART' in s.title.upper()]
    notebook_parts = [s for s in notebook_sections if s.level == 1 and 'PART' in s.title.upper()]
    
    print(f"\nPART sections:")
    print(f"  Hierarchical: {len(hierarchical_parts)}")
    print(f"  Notebook-style: {len(notebook_parts)}")
    
    if hierarchical_parts:
        print(f"\n  Hierarchical PART titles:")
        for part in hierarchical_parts:
            print(f"    - {part.title}")
    
    if notebook_parts:
        print(f"\n  Notebook-style PART titles:")
        for part in notebook_parts:
            print(f"    - {part.title}")
    
    # Compare numbered articles
    hierarchical_articles = [s for s in flat_hierarchical if s.level == 2 and any(c.isdigit() for c in s.title[:5])]
    notebook_articles = [s for s in notebook_sections if s.level == 2 and any(c.isdigit() for c in s.title[:5])]
    
    print(f"\nNumbered articles (level 2):")
    print(f"  Hierarchical: {len(hierarchical_articles)}")
    print(f"  Notebook-style: {len(notebook_articles)}")
    
    if notebook_articles:
        print(f"\n  Notebook-style article titles (first 10):")
        for article in notebook_articles[:10]:
            print(f"    - {article.title}")


def main():
    """Main test function."""
    # Test with real CSI specification
    spec_path = Path("data/parsed/Spec 14 24 00 - Hydraulic Elevators_redacted_20251021_172135.md")
    
    if not spec_path.exists():
        print(f"Error: Document not found at {spec_path}")
        print("\nAvailable documents:")
        for md_file in Path("data/parsed").glob("*.md"):
            print(f"  - {md_file}")
        return 1
    
    print(f"Loading document: {spec_path.name}")
    markdown_content = spec_path.read_text(encoding='utf-8')
    
    compare_modes(markdown_content, spec_path.name)
    
    print("\n\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print("\nKey Findings:")
    print("1. Check if PART sections are correctly detected in both modes")
    print("2. Check if numbered articles (e.g., '1.1 SUMMARY') are properly anchored")
    print("3. Compare section counts and content distribution")
    print("4. Verify header paths are correctly built")
    print("5. Check if imputed PARTs are created when needed")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

