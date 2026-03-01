#!/usr/bin/env python3
"""
Script to copy tree_xxxx.json files to their respective folders in ../Tipitaka.org
and rename them to tree.json
"""

import os
import shutil
import sys

# List of script codes to process
# Add or remove script codes as needed
SCRIPT_CODES = [
    "beng",  # Bengali
    "cyrl",  # Cyrillic
    "gujr",  # Gujarati
    "guru",  # Gurmukhi
    "khmr",  # Khmer
    "knda",  # Kannada
    "mlym",  # Malay
    "mymr",  # Myanmar
    "romn",  # Roman
    "sinh",  # Sinhala
    "telu",  # Telugu 
    "thai",  # Thai
    "tibt",  # Tibetan
]

def copy_tree_files(script_codes):
    """
    Copy tree_<script>.json files to ../Tipitaka.org/<script>/tree.json
    
    Args:
        script_codes: List of script codes to process
    """
    # Get the current directory
    current_dir = os.getcwd()
    
    # Define the target base directory (relative to current directory)
    target_base = os.path.join("..\..\..\..", "Tipitaka.org")
    
    # Check if target base directory exists
    if not os.path.exists(target_base):
        print(f"Error: Target directory '{target_base}' does not exist!")
        sys.exit(1)
    
    print(f"Current directory: {current_dir}")
    print(f"Target base directory: {os.path.abspath(target_base)}")
    print("-" * 50)
    
    # Process each script code
    for script in script_codes:
        source_file = f"tree_{script}.json"
        target_dir = os.path.join(target_base, script)
        target_file = os.path.join(target_dir, "tree.json")
        
        print(f"Processing {script}...")
        
        # Check if source file exists
        if not os.path.exists(source_file):
            print(f"  Warning: Source file '{source_file}' not found, skipping...")
            continue
        
        # Check if target directory exists
        if not os.path.exists(target_dir):
            print(f"  Error: Target directory '{target_dir}' does not exist!")
            continue
        
        # Remove existing tree.json if it exists
        if os.path.exists(target_file):
            try:
                if os.path.isfile(target_file):
                    os.remove(target_file)
                    print(f"  Removed existing file: {target_file}")
                else:
                    print(f"  Warning: '{target_file}' exists but is not a file, skipping removal...")
            except Exception as e:
                print(f"  Error removing existing file: {e}")
                continue
        
        # Copy the file
        try:
            shutil.copy2(source_file, target_file)  # copy2 preserves metadata
            print(f"  Copied '{source_file}' to '{target_file}'")
        except Exception as e:
            print(f"  Error copying file: {e}")
    
    print("-" * 50)
    print("Process completed!")

def main():
    """Main function to run the script"""
    print("Tree JSON File Copier")
    print("=" * 50)
    
    # Use the predefined list, but allow command line arguments to override
    if len(sys.argv) > 1:
        # If command line arguments are provided, use them instead
        script_codes = sys.argv[1:]
        print(f"Using script codes from command line: {', '.join(script_codes)}")
    else:
        script_codes = SCRIPT_CODES
        print(f"Using default script codes: {', '.join(script_codes)}")
    
    # Confirm with user before proceeding
    print("\nThis script will:")
    for script in script_codes:
        print(f"  - Copy 'tree_{script}.json' to '../Tipitaka.org/{script}/tree.json'")
        print(f"    (removing existing tree.json if present)")
    
    response = input("\nDo you want to proceed? (y/n): ").strip().lower()
    if response == 'y' or response == 'yes':
        copy_tree_files(script_codes)
    else:
        print("Operation cancelled.")

if __name__ == "__main__":
    main()