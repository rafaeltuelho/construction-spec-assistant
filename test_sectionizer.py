#!/usr/bin/env python
"""Test script for sectionizer refactoring."""

import sys
sys.path.insert(0, 'backend')

from app.core.sectionizer import sectionize_markdown, flatten_sections

# Sample CSI markdown
sample_markdown = """
PART 1 - GENERAL

1.1 SUMMARY

This section specifies hydraulic elevators.

1.2 REFERENCES

A. ASME A17.1 - Safety Code for Elevators and Escalators
B. ASME A17.2 - Guide for Inspection

PART 2 - PRODUCTS

2.1 MANUFACTURERS

A. ThyssenKrupp Elevator
B. Otis Elevator Company

2.2 MATERIALS

1. Steel components
2. Hydraulic fluid
"""

print("=" * 80)
print("Testing HIERARCHICAL sectionization (default)...")
print("=" * 80)
sections = sectionize_markdown(sample_markdown, use_notebook_logic=False)

print(f"\nFound {len(sections)} top-level sections")
for section in sections:
    print(f"\nSection: {section.title}")
    print(f"  Level: {section.level}")
    print(f"  Section ID: {section.section_id}")
    print(f"  Header Path: {section.header_path}")
    print(f"  Page Start: {section.page_start}")
    print(f"  Page End: {section.page_end}")
    print(f"  Content length: {len(section.content)} chars")
    print(f"  Subsections: {len(section.subsections)}")

    for subsection in section.subsections:
        print(f"    - {subsection.title} (level {subsection.level}, id={subsection.section_id})")
        print(f"      Header Path: {subsection.header_path}")

print("\n\nFlattened sections:")
flat = flatten_sections(sections)
print(f"Total sections (flattened): {len(flat)}")
for idx, section in enumerate(flat):
    print(f"{idx+1}. {' > '.join(section.header_path)} (id={section.section_id})")

print("\n\n")
print("=" * 80)
print("Testing NOTEBOOK-STYLE sectionization (flat with CSI-aware heuristics)...")
print("=" * 80)
notebook_sections = sectionize_markdown(sample_markdown, use_notebook_logic=True)

print(f"\nFound {len(notebook_sections)} sections (flat list)")
for idx, section in enumerate(notebook_sections):
    print(f"\n{idx+1}. Section: {section.title}")
    print(f"   Level: {section.level}")
    print(f"   Section ID: {section.section_id}")
    print(f"   Header Path: {' > '.join(section.header_path)}")
    print(f"   Content length: {len(section.content)} chars")
    print(f"   Content preview: {section.content[:100]}..." if len(section.content) > 100 else f"   Content: {section.content}")

