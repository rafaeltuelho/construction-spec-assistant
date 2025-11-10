"""
Test script for JSON parsing with json-repair fallback.

This script tests various JSON response formats to ensure robust parsing.
"""

import json
from json_repair import repair_json


def test_json_parsing():
    """Test various JSON response formats."""
    
    test_cases = [
        {
            "name": "Valid JSON",
            "input": '{"verdict": "consistent", "confidence": 0.9, "submittal_evidence": "Capacity: 3500 lbs", "reasoning": "Meets requirement", "primary_source": "submittal"}',
            "should_parse": True,
            "should_repair": False,
        },
        {
            "name": "JSON with markdown code fences",
            "input": '```json\n{"verdict": "consistent", "confidence": 0.9, "submittal_evidence": "Capacity: 3500 lbs", "reasoning": "Meets requirement", "primary_source": "submittal"}\n```',
            "should_parse": False,
            "should_repair": True,
        },
        {
            "name": "JSON with single quotes",
            "input": "{'verdict': 'consistent', 'confidence': 0.9, 'submittal_evidence': 'Capacity: 3500 lbs', 'reasoning': 'Meets requirement', 'primary_source': 'submittal'}",
            "should_parse": False,
            "should_repair": True,
        },
        {
            "name": "JSON with trailing comma",
            "input": '{"verdict": "consistent", "confidence": 0.9, "submittal_evidence": "Capacity: 3500 lbs", "reasoning": "Meets requirement", "primary_source": "submittal",}',
            "should_parse": False,
            "should_repair": True,
        },
        {
            "name": "JSON with comments",
            "input": '{"verdict": "consistent", /* this is a comment */ "confidence": 0.9, "submittal_evidence": "Capacity: 3500 lbs", "reasoning": "Meets requirement", "primary_source": "submittal"}',
            "should_parse": False,
            "should_repair": True,
        },
        {
            "name": "JSON with explanatory text before",
            "input": 'Here is my analysis:\n{"verdict": "consistent", "confidence": 0.9, "submittal_evidence": "Capacity: 3500 lbs", "reasoning": "Meets requirement", "primary_source": "submittal"}',
            "should_parse": False,
            "should_repair": True,
        },
        {
            "name": "JSON with explanatory text after",
            "input": '{"verdict": "consistent", "confidence": 0.9, "submittal_evidence": "Capacity: 3500 lbs", "reasoning": "Meets requirement", "primary_source": "submittal"}\nThis is my conclusion.',
            "should_parse": False,
            "should_repair": True,
        },
        {
            "name": "Malformed JSON - missing closing brace",
            "input": '{"verdict": "consistent", "confidence": 0.9, "submittal_evidence": "Capacity: 3500 lbs", "reasoning": "Meets requirement", "primary_source": "submittal"',
            "should_parse": False,
            "should_repair": True,
        },
        {
            "name": "Malformed JSON - unquoted keys",
            "input": '{verdict: "consistent", confidence: 0.9, submittal_evidence: "Capacity: 3500 lbs", reasoning: "Meets requirement", primary_source: "submittal"}',
            "should_parse": False,
            "should_repair": True,
        },
    ]
    
    print("=" * 80)
    print("JSON PARSING TEST SUITE")
    print("=" * 80)
    print()
    
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"Test {i}: {test_case['name']}")
        print("-" * 80)
        
        input_text = test_case["input"]
        print(f"Input (first 100 chars): {input_text[:100]}...")
        print()
        
        # Test standard JSON parsing
        try:
            result = json.loads(input_text)
            parsed_standard = True
            print("✅ Standard JSON parsing: SUCCESS")
        except json.JSONDecodeError as e:
            parsed_standard = False
            print(f"❌ Standard JSON parsing: FAILED - {e}")
        
        # Test with repair
        repaired = False
        if not parsed_standard:
            try:
                # Strip markdown code fences if present
                cleaned_content = input_text.strip()
                if cleaned_content.startswith("```json"):
                    cleaned_content = cleaned_content[7:]
                elif cleaned_content.startswith("```"):
                    cleaned_content = cleaned_content[3:]
                if cleaned_content.endswith("```"):
                    cleaned_content = cleaned_content[:-3]
                cleaned_content = cleaned_content.strip()
                
                # Attempt repair
                repaired_json = repair_json(cleaned_content)
                result = json.loads(repaired_json)
                repaired = True
                print("✅ JSON repair: SUCCESS")
                print(f"   Repaired JSON (first 100 chars): {repaired_json[:100]}...")
            except Exception as repair_error:
                print(f"❌ JSON repair: FAILED - {repair_error}")
        
        # Validate expectations
        if test_case["should_parse"] and parsed_standard:
            print("✅ Test PASSED: Parsed as expected")
            passed += 1
        elif test_case["should_repair"] and repaired:
            print("✅ Test PASSED: Repaired as expected")
            passed += 1
        elif not test_case["should_parse"] and not test_case["should_repair"]:
            if not parsed_standard and not repaired:
                print("✅ Test PASSED: Failed as expected")
                passed += 1
            else:
                print("❌ Test FAILED: Should have failed but succeeded")
                failed += 1
        else:
            print("❌ Test FAILED: Did not meet expectations")
            failed += 1
        
        print()
    
    print("=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 80)
    
    return passed, failed


if __name__ == "__main__":
    passed, failed = test_json_parsing()
    exit(0 if failed == 0 else 1)

