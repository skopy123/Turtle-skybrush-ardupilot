#!/usr/bin/env python3
"""
Script to find STM32H7 boards with bidirectional DShot (BIDIR) support.
Recursively searches hwdef.dat files, expands includes, and reports findings.
"""

import os
import re
from pathlib import Path
from typing import List, Tuple, Optional


def expand_includes(file_path: Path, content: str, current_depth: int = 0, max_depth: int = 2) -> str:
    """
    Expand include directives in hwdef content.
    
    Args:
        file_path: Path to the current hwdef file
        content: Content of the file
        current_depth: Current include depth (0 = original file)
        max_depth: Maximum include depth (default 2)
    
    Returns:
        Content with includes expanded
    """
    if current_depth >= max_depth:
        return content
    
    lines = content.split('\n')
    result_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        # Check if line starts with "include"
        if stripped.startswith('include '):
            # Extract the include path
            include_path_str = stripped[8:].strip()  # Remove "include " prefix
            
            # Resolve relative path
            include_file = file_path.parent / include_path_str
            
            try:
                # Read the included file
                with open(include_file, 'r', encoding='utf-8', errors='ignore') as f:
                    included_content = f.read()
                
                # Recursively expand includes in the included file
                expanded_content = expand_includes(include_file, included_content, current_depth + 1, max_depth)
                
                # Add a comment to mark where the include was
                result_lines.append(f"# === Included from {include_path_str} ===")
                result_lines.append(expanded_content)
                result_lines.append(f"# === End of {include_path_str} ===")
            except FileNotFoundError:
                # If include file not found, keep the original line and add a warning
                result_lines.append(f"# WARNING: Include file not found: {include_path_str}")
                result_lines.append(line)
            except Exception as e:
                # Other errors - keep original line with warning
                result_lines.append(f"# WARNING: Error reading {include_path_str}: {e}")
                result_lines.append(line)
        else:
            # Not an include line, keep as-is
            result_lines.append(line)
    
    return '\n'.join(result_lines)


def is_line_commented(line: str) -> bool:
    """Check if a line is commented out."""
    stripped = line.strip()
    return stripped.startswith('#')


def check_mcu_type(content: str) -> Tuple[bool, Optional[str]]:
    """
    Check if the MCU type is STM32H7.
    
    Args:
        content: Expanded file content
    
    Returns:
        Tuple of (is_h7, mcu_line)
    """
    for line in content.split('\n'):
        if is_line_commented(line):
            continue
        
        stripped = line.strip()
        if stripped.startswith('MCU '):
            # Check if line contains STM32H7
            if 'STM32H7' in line:
                return True, line.strip()
            else:
                return False, line.strip()
    
    return False, None


def find_bidir_lines(content: str) -> List[str]:
    """
    Find all lines that contain PWM and end with BIDIR (non-commented).
    
    Args:
        content: Expanded file content
    
    Returns:
        List of BIDIR PWM lines
    """
    bidir_lines = []
    
    for line in content.split('\n'):
        if is_line_commented(line):
            continue
        
        stripped = line.strip()
        
        # Check if line contains PWM and ends with BIDIR
        if 'PWM' in line and stripped.endswith('BIDIR'):
            bidir_lines.append(line.rstrip())
    
    return bidir_lines


def find_all_pwm_lines(content: str) -> List[str]:
    """
    Find all lines that contain PWM (non-commented).
    
    Args:
        content: Expanded file content
    
    Returns:
        List of all PWM lines
    """
    pwm_lines = []
    
    for line in content.split('\n'):
        if is_line_commented(line):
            continue
        
        # Check if line contains PWM
        if 'PWM' in line:
            pwm_lines.append(line.rstrip())
    
    return pwm_lines


def process_hwdef_file(file_path: Path) -> Optional[Tuple[str, str, List[str], List[str]]]:
    """
    Process a single hwdef.dat file.
    
    Args:
        file_path: Path to hwdef.dat file
    
    Returns:
        Tuple of (status_message, file_path_str, bidir_lines, all_pwm_lines) or None if rejected
    """
    try:
        # Read the file
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Stage 1: Expand includes
        expanded_content = expand_includes(file_path, content)
        
        # Stage 2: Check MCU type
        is_h7, mcu_line = check_mcu_type(expanded_content)
        if not is_h7:
            return ("Not H7 MCU", str(file_path), [], [])
        
        # Stage 3: Find BIDIR lines
        bidir_lines = find_bidir_lines(expanded_content)
        if not bidir_lines:
            return ("No Bidir support", str(file_path), [], [])
        
        # Stage 4: Success - H7 with BIDIR support, get all PWM lines
        all_pwm_lines = find_all_pwm_lines(expanded_content)
        return ("H7 cpu with BIDIR support", str(file_path), bidir_lines, all_pwm_lines)
    
    except Exception as e:
        return (f"Error processing file: {e}", str(file_path), [], [])


def find_hwdef_files(root_dir: Path) -> List[Path]:
    """
    Recursively find all hwdef.dat files in subdirectories.
    
    Args:
        root_dir: Root directory to search
    
    Returns:
        List of paths to hwdef.dat files
    """
    hwdef_files = []
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        if 'hwdef.dat' in filenames:
            hwdef_files.append(Path(dirpath) / 'hwdef.dat')
    
    return hwdef_files


def main():
    """Main execution function."""
    # Get the script's directory (hwdef folder)
    script_dir = Path(__file__).parent
    
    print(f"Searching for hwdef.dat files in: {script_dir}")
    print("=" * 80)
    
    # Find all hwdef.dat files
    hwdef_files = find_hwdef_files(script_dir)
    print(f"Found {len(hwdef_files)} hwdef.dat files\n")
    
    # Process all files and collect results
    results = []
    for hwdef_file in hwdef_files:
        result = process_hwdef_file(hwdef_file)
        if result:
            results.append(result)
    
    # Group results by status
    h7_bidir_boards = []
    not_h7_boards = []
    no_bidir_boards = []
    error_boards = []
    
    for status, filepath, bidir_lines, all_pwm_lines in results:
        if status == "H7 cpu with BIDIR support":
            h7_bidir_boards.append((filepath, bidir_lines, all_pwm_lines))
        elif status == "Not H7 MCU":
            not_h7_boards.append(filepath)
        elif status == "No Bidir support":
            no_bidir_boards.append(filepath)
        else:
            error_boards.append((filepath, status))
    
    # Sort each group by filepath (board name)
    h7_bidir_boards.sort(key=lambda x: x[0])
    not_h7_boards.sort()
    no_bidir_boards.sort()
    error_boards.sort(key=lambda x: x[0])
    
    # Print results - H7 boards with BIDIR support (detailed PWM info)
    print("\n" + "=" * 80)
    print("RESULTS - H7 BOARDS WITH BIDIR SUPPORT")
    print("=" * 80)
    for filepath, bidir_lines, all_pwm_lines in h7_bidir_boards:
        board_name = Path(filepath).parent.name
        print(f"\nFile {filepath} H7 cpu with BIDIR support")
        print(f"  Board: {board_name}")
        print(f"  Total PWM outputs: {len(all_pwm_lines)}")
        print(f"  BIDIR outputs: {len(bidir_lines)}")
        print(f"\n  All PWM outputs:")
        for line in all_pwm_lines:
            if line.strip().endswith('BIDIR'):
                print(f"    {line} <-- BIDIR")
            else:
                print(f"    {line}")
    
    print("\n" + "=" * 80)
    print("RESULTS - NOT H7 MCU")
    print("=" * 80)
    for filepath in not_h7_boards:
        print(f"File {filepath} Not H7 MCU")
    
    print("\n" + "=" * 80)
    print("RESULTS - NO BIDIR SUPPORT")
    print("=" * 80)
    for filepath in no_bidir_boards:
        print(f"File {filepath} No Bidir support")
    
    if error_boards:
        print("\n" + "=" * 80)
        print("RESULTS - ERRORS")
        print("=" * 80)
        for filepath, error_msg in error_boards:
            print(f"File {filepath} {error_msg}")
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total files processed: {len(results)}")
    print(f"H7 boards with BIDIR support: {len(h7_bidir_boards)}")
    print(f"Not H7 MCU: {len(not_h7_boards)}")
    print(f"H7 but no BIDIR support: {len(no_bidir_boards)}")
    if error_boards:
        print(f"Errors: {len(error_boards)}")
    
    # Grouped summary by board characteristics
    print("\n" + "=" * 80)
    print("GROUPED SUMMARY - H7 BIDIR BOARDS BY PWM COUNT")
    print("=" * 80)
    
    # Group by PWM count
    pwm_count_groups = {}
    for filepath, bidir_lines, all_pwm_lines in h7_bidir_boards:
        board_name = Path(filepath).parent.name
        pwm_count = len(all_pwm_lines)
        bidir_count = len(bidir_lines)
        key = f"{pwm_count} PWM outputs ({bidir_count} BIDIR)"
        if key not in pwm_count_groups:
            pwm_count_groups[key] = []
        pwm_count_groups[key].append(board_name)
    
    for key in sorted(pwm_count_groups.keys()):
        boards = pwm_count_groups[key]
        print(f"\n{key}: {len(boards)} boards")
        for board in sorted(boards):
            print(f"  - {board}")
    
    # Summary by BIDIR ratio
    print("\n" + "=" * 80)
    print("GROUPED SUMMARY - H7 BIDIR BOARDS BY BIDIR RATIO")
    print("=" * 80)
    
    bidir_ratio_groups = {
        "All PWM outputs are BIDIR (100%)": [],
        "More than half BIDIR (>50%)": [],
        "Half BIDIR (50%)": [],
        "Less than half BIDIR (<50%)": []
    }
    
    for filepath, bidir_lines, all_pwm_lines in h7_bidir_boards:
        board_name = Path(filepath).parent.name
        pwm_count = len(all_pwm_lines)
        bidir_count = len(bidir_lines)
        
        if pwm_count == 0:
            continue
            
        ratio = bidir_count / pwm_count
        
        if ratio == 1.0:
            bidir_ratio_groups["All PWM outputs are BIDIR (100%)"].append(board_name)
        elif ratio > 0.5:
            bidir_ratio_groups["More than half BIDIR (>50%)"].append(board_name)
        elif ratio == 0.5:
            bidir_ratio_groups["Half BIDIR (50%)"].append(board_name)
        else:
            bidir_ratio_groups["Less than half BIDIR (<50%)"].append(board_name)
    
    for category in ["All PWM outputs are BIDIR (100%)", "More than half BIDIR (>50%)", 
                     "Half BIDIR (50%)", "Less than half BIDIR (<50%)"]:
        boards = bidir_ratio_groups[category]
        if boards:
            print(f"\n{category}: {len(boards)} boards")
            for board in sorted(boards):
                print(f"  - {board}")


if __name__ == "__main__":
    main()
