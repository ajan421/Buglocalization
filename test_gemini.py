"""
Quick test script to verify Gemini API is working
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def test_gemini():
    """Test Gemini API connection"""
    print("=" * 60)
    print("TESTING GEMINI API")
    print("=" * 60)
    
    # Check if API key is set
    print("\n1. Checking for API key...")
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("   ✗ GEMINI_API_KEY not found!")
        print("\n   To set it:")
        print("   Option 1 (Recommended): Create a .env file")
        print("     1. Copy .env.example to .env")
        print("     2. Edit .env and add your API key")
        print("\n   Option 2: Set environment variable")
        print("     Windows: $env:GEMINI_API_KEY='your-key'")
        print("     Linux/Mac: export GEMINI_API_KEY='your-key'")
        print("\n   Get your key from: https://makersuite.google.com/app/apikey")
        return False
    
    print(f"   ✓ API key found (length: {len(api_key)} chars)")
    
    # Try to import the library
    print("\n2. Checking google-generativeai library...")
    try:
        import google.generativeai as genai
        print("   ✓ Library installed")
    except ImportError:
        print("   ✗ Library not found!")
        print("\n   Install it with: pip install google-generativeai")
        return False
    
    # Try to connect and test
    print("\n3. Testing API connection...")
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        print("   Sending test request...")
        response = model.generate_content("Say 'Hello! Gemini is working!' in one sentence.")
        
        print("   ✓ API connection successful!")
        print(f"\n   Response: {response.text}")
        return True
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        print("\n   Possible issues:")
        print("   - Invalid API key")
        print("   - Network connection problem")
        print("   - API quota exceeded")
        return False

def test_bug_analysis():
    """Test bug report analysis"""
    print("\n" + "=" * 60)
    print("TESTING BUG ANALYSIS")
    print("=" * 60)
    
    try:
        import google.generativeai as genai
        
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            print("⚠ Skipping (no API key)")
            return
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        sample_bug = """
Bug: NullPointerException in org.aspectj.weaver.World.resolve()
Stack trace shows error at line 456 in World.java
Related to BcelWorld class
"""
        
        prompt = f"""Analyze this bug report and extract key information as JSON:
{sample_bug}

Return JSON with: summary, error_type, keywords, potential_classes"""
        
        print("\nSending bug analysis request...")
        response = model.generate_content(prompt)
        print("✓ Bug analysis successful!")
        print(f"\nAnalysis:\n{response.text}")
        
    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════╗
║          Gemini API Test Script                          ║
╚══════════════════════════════════════════════════════════╝
""")
    
    success = test_gemini()
    
    if success:
        test_bug_analysis()
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("\nGemini is ready to use for bug localization.")
        print("You can now run: python main.py")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("✗ TESTS FAILED")
        print("Please fix the issues above before running main.py")
        print("=" * 60)
        sys.exit(1)

