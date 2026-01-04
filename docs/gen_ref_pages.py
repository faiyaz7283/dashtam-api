"""Generate API reference pages automatically from source code.

This script is run by mkdocs-gen-files plugin during docs build.
It discovers all Python modules in src/ and creates corresponding
reference pages with mkdocstrings directives.
"""

from pathlib import Path

import mkdocs_gen_files

# Root of the source code
src_root = Path("src")

# Navigation items for literate-nav
nav = mkdocs_gen_files.Nav()  # type: ignore[attr-defined,no-untyped-call]

# Iterate through all Python files in src/
for path in sorted(src_root.rglob("*.py")):
    # Skip __pycache__ and other non-source files
    if "__pycache__" in str(path):
        continue
    
    # Get module path relative to src/
    module_path = path.relative_to(src_root).with_suffix("")
    
    # Convert path to Python module notation
    # e.g., src/domain/entities/user.py -> domain.entities.user
    doc_path = path.relative_to(src_root).with_suffix(".md")
    full_doc_path = Path("reference") / doc_path
    
    # Convert file path to Python import path
    parts = tuple(module_path.parts)
    
    # Skip __init__ files in navigation (but still generate them)
    if parts[-1] == "__init__":
        continue
    
    # Build Python module path
    module_name = ".".join(["src"] + list(parts))
    
    # Add to navigation
    nav[parts] = doc_path.as_posix()
    
    # Create the reference page
    with mkdocs_gen_files.open(full_doc_path, "w") as fd:
        # Write page title
        identifier = ".".join(parts)
        print(f"# `{identifier}`", file=fd)
        print("", file=fd)
        
        # Write mkdocstrings directive
        print(f"::: {module_name}", file=fd)
        print("    options:", file=fd)
        print("      show_root_heading: true", file=fd)
        print("      show_source: true", file=fd)
        print("      members_order: source", file=fd)
        print("      group_by_category: true", file=fd)
        print("      show_bases: true", file=fd)
        print("      show_signature_annotations: true", file=fd)
        print("      separate_signature: true", file=fd)
    
    # Set edit path for GitHub edit links
    mkdocs_gen_files.set_edit_path(full_doc_path, Path("..") / path)

# Write navigation file for literate-nav
with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())
