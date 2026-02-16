"""
Quick LLM Test with Ollama phi3:mini

This script tests the LLM integration with phi3:mini model.
"""

import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent
sys.path.insert(0, str(parent_dir))

from governance_core.llm_provider import OllamaProvider

def test_ollama_phi3():
    print("=" * 80)
    print("TESTING OLLAMA PHI3:MINI INTEGRATION")
    print("=" * 80)
    
    # Step 1: Check if Ollama is available
    print("\n1️⃣  Checking Ollama availability...")
    provider = OllamaProvider(model="phi3:mini")
    
    if not provider.is_available():
        print("❌ Ollama is not available or phi3:mini model not found")
        print("\nTo fix this, run:")
        print("   ollama pull phi3:mini")
        return False
    
    print(f"✅ Ollama is available: {provider.provider_name}")
    
    # Step 2: Test simple text generation
    print("\n2️⃣  Testing text generation...")
    prompt = "Explain what data leakage is in one sentence."
    
    try:
        response = provider.generate(
            prompt=prompt,
            system_prompt="You are a data privacy expert. Be concise.",
            temperature=0.1,
            max_tokens=100
        )
        print(f"✅ Generation successful!")
        print(f"\nPrompt: {prompt}")
        print(f"Response: {response[:200]}...")
        
    except Exception as e:
        print(f"❌ Generation failed: {e}")
        return False
    
    # Step 3: Test JSON generation
    print("\n3️⃣  Testing JSON generation...")
    json_prompt = """
    Analyze this synthetic data evaluation result:
    - Privacy score: 0.85
    - Leakage risk: low
    - Near-duplicates: 2
    
    Provide a decision (ACCEPT/REJECT/REVIEW) and brief justification.
    """
    
    try:
        json_response = provider.generate_json(
            prompt=json_prompt,
            system_prompt="You are a data governance expert. Respond in JSON format with 'decision' and 'justification' fields.",
        )
        print(f"✅ JSON generation successful!")
        print(f"\nJSON Response:")
        import json
        print(json.dumps(json_response, indent=2))
        
    except Exception as e:
        print(f"❌ JSON generation failed: {e}")
        print("   This is expected with some models - text generation still works!")
    
    print("\n" + "=" * 80)
    print("✅ PHI3:MINI TEST COMPLETE")
    print("=" * 80)
    return True

if __name__ == "__main__":
    success = test_ollama_phi3()
    sys.exit(0 if success else 1)
