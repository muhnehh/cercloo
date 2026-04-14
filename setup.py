"""
SETUP HELPER - Check prerequisites and install dependencies
===========================================================

This script makes sure everything is ready to run the project.
Run this FIRST before anything else.
"""

import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd: str, description: str = "") -> bool:
    """Run a shell command, return True if successful."""
    if description:
        print(f"\n  {description}...", end=" ")
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        if result.returncode == 0:
            print("✓")
            return True
        else:
            print("✗")
            return False
    except subprocess.TimeoutExpired:
        print("✗ (timeout)")
        return False
    except Exception as e:
        print(f"✗ ({e})")
        return False


def check_python() -> bool:
    """Check Python 3.10+ is available."""
    print("\n📋 Checking Python environment...")
    
    version = sys.version_info
    if version.major == 3 and version.minor >= 10:
        print(f"  ✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"  ✗ Python {version.major}.{version.minor} (need 3.10+)")
        return False


def check_pandas() -> bool:
    """Check pandas is installed."""
    print("\n📊 Checking pandas...")
    try:
        import pandas as pd
        print(f"  ✓ pandas {pd.__version__}")
        return True
    except ImportError:
        print("  ✗ pandas not installed")
        return False


def install_dependencies() -> bool:
    """Install required Python packages."""
    print("\n📦 Installing Python dependencies...")
    
    packages = [
        "pandas>=2.0",
        "anthropic>=0.7",  # For Claude API (optional, if user has key)
        "requests>=2.31",  # For Ollama HTTP calls
    ]
    
    for pkg in packages:
        print(f"  • {pkg.split('>=')[0]}...", end=" ")
        cmd = f'"{sys.executable}" -m pip install "{pkg}" --quiet'
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=30)
            if result.returncode == 0:
                print("✓")
            else:
                print("✗")
                return False
        except Exception as e:
            print(f"✗ ({e})")
            return False
    
    return True


def check_ollama() -> bool:
    """Check if Ollama is installed and running."""
    print("\n🤖 Checking Ollama...")
    
    # Check if ollama command exists
    ollama_installed = run_command("ollama --version", "Checking ollama installation")
    
    if not ollama_installed:
        print("\n  ⚠️  Ollama not installed (but you can still use Claude API)")
        print("  Install from: https://ollama.ai")
        return False
    
    # Check if Ollama server is running
    print("\n  Checking if Ollama server is running...")
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            models = response.json().get("models", [])
            if models:
                model_names = [m["name"] for m in models]
                print(f"  ✓ Ollama server running with models: {', '.join(model_names)}")
                return True
            else:
                print("  ⚠️  Ollama running but no models installed")
                print("     Run: ollama pull mistral")
                return False
        else:
            print("  ✗ Ollama server not responding")
            return False
    except requests.exceptions.ConnectionError:
        print("  ✗ Ollama server not running on localhost:11434")
        print("     Start it: ollama serve")
        return False
    except Exception as e:
        print(f"  ✗ Error checking Ollama: {e}")
        return False


def check_data_files() -> bool:
    """Check if data files exist."""
    print("\n📁 Checking data files...")
    
    required_files = [
        "datasets/employee_master.csv",
        "datasets/payroll_run.csv",
        "datasets/leave_records.csv",
    ]
    
    all_exist = True
    for file in required_files:
        if Path(file).exists():
            print(f"  ✓ {file}")
        else:
            print(f"  ✗ {file} (missing)")
            all_exist = False
    
    return all_exist


def main():
    print("\n" + "="*70)
    print("CERCLI HR PLATFORM - SETUP CHECK")
    print("="*70)
    
    checks = [
        ("Python 3.10+", check_python),
        ("pandas", check_pandas),
        ("Data files", check_data_files),
    ]
    
    passed = 0
    for name, check_func in checks:
        if check_func():
            passed += 1
    
    # Optional: install deps
    print(f"\n✓ Passed {passed}/{len(checks)} checks")
    
    if passed == len(checks):
        print("\n🔧 Installing/updating Python dependencies...")
        if install_dependencies():
            print("\n✓ Dependencies installed")
        else:
            print("\n✗ Failed to install dependencies")
            return False
    else:
        print("\n✗ Fix the above issues first")
        return False
    
    # Check Ollama (optional but recommended)
    print("\n" + "="*70)
    print("OPTIONAL: LLM Setup (one of these)")
    print("="*70)
    
    ollama_ok = check_ollama()
    
    # Check Claude
    if os.environ.get("ANTHROPIC_API_KEY"):
        print("\n✓ ANTHROPIC_API_KEY is set (Claude available as fallback)")
    else:
        print("\n⚠️  ANTHROPIC_API_KEY not set (Claude not available)")
        if not ollama_ok:
            print("\n⚠️  Neither Ollama nor Claude API available!")
            print("   Install Ollama OR set ANTHROPIC_API_KEY")
    
    # Final summary
    print("\n" + "="*70)
    print("NEXT STEPS")
    print("="*70)
    
    if ollama_ok:
        print("\n✓ Ready to go! Run:")
        print("  python src/mapper.py")
    else:
        print("\n1. Install Ollama from https://ollama.ai")
        print("2. Run: ollama pull mistral")
        print("3. Run: ollama serve (in separate terminal)")
        print("4. Then run: python src/mapper.py")
        print("\nOR set ANTHROPIC_API_KEY if you have Claude API access")
    
    print("\n" + "="*70 + "\n")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
