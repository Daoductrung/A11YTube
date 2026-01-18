import ast
import os
import sys
import time

def extract_strings(root_dir):
    strings = {}
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Scan python files
        for filename in filenames:
            if filename.endswith(".py"):
                filepath = os.path.join(dirpath, filename)
                relpath = os.path.relpath(filepath, root_dir)
                
                with open(filepath, "r", encoding="utf-8") as f:
                    try:
                        tree = ast.parse(f.read(), filename=filepath)
                    except SyntaxError:
                        continue
                        
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id == "_":
                            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                                s = node.args[0].value
                                if s not in strings:
                                    strings[s] = []
                                strings[s].append((relpath, node.lineno))
    return strings


def write_pot(strings, outfile):
    timestamp = time.strftime('%Y-%m-%d %H:%M%z')
    content = f"""# A11YTube English Translation Template
# Copyright (C) YEAR THE PACKAGE'S COPYRIGHT HOLDER
# This file is distributed under the same license as the PACKAGE package.
# FIRST AUTHOR <EMAIL@ADDRESS>, YEAR.
#
#, fuzzy
msgid ""
msgstr ""
"Project-Id-Version: A11YTube 0.2.5\\n"
"Report-Msgid-Bugs-To: \\n"
"POT-Creation-Date: {timestamp}\\n"
"PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\\n"
"Last-Translator: FULL NAME <EMAIL@ADDRESS>\\n"
"Language-Team: LANGUAGE <LL@li.org>\\n"
"Language: en\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"

"""
    sorted_strings = sorted(strings.keys())
    
    for s in sorted_strings:
        locations = strings[s]
        for relpath, lineno in locations:
            content += f"#: {relpath}:{lineno}\n"
        
        # Escape string
        esc_s = s.replace('"', '\\"').replace('\n', '\\n')
        content += f'msgid "{esc_s}"\n'
        content += 'msgstr ""\n\n'
        
    os.makedirs(os.path.dirname(outfile), exist_ok=True)
    with open(outfile, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Wrote {len(strings)} strings to {outfile}")


def parse_po(filepath):
    """
    Parses a PO file into a header and a dictionary of message strings.
    Handles multiline msgid/msgstr and standard PO escaping.
    """
    if not os.path.exists(filepath):
        return [], {}

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    header = []
    messages = {}
    current_msgid = None
    current_msgstr = None
    in_header = True
    state = "none" # none, msgid, msgstr

    for line in lines:
        line = line.strip()
        
        # Header collection
        if in_header:
            if line.startswith('msgid ""'):
                in_header = False
                # Start of the header entry (metadata) inside msgstr
                current_msgid = ""
                state = "msgid" 
                continue
            if line.startswith("#"):
                header.append(line)
                continue
            if not line:
                 header.append("")
                 continue
        
        # Skip comments after header
        if line.startswith("#"):
            continue

        if not line:
            continue

        if line.startswith('msgid "'):
            # Save previous
            if current_msgid is not None and current_msgstr is not None:
                # Store EXACTLY as it appeared (escaped form) to key it
                # But actually we want the logical key.
                # However, our update logic compares with *unescaped* source strings.
                # So we must UNESCAPE the found keys to match source.
                pass 
                
            # Finish previous entry
            if current_msgid is not None and current_msgstr is not None:
                # Don't add if it's the header entry (empty msgid)
                if current_msgid != "":
                     messages[current_msgid] = current_msgstr

            raw_val = line[7:-1] 
            current_msgid = raw_val
            current_msgstr = None 
            state = "msgid"
        
        elif line.startswith('msgstr "'):
            raw_val = line[8:-1]
            current_msgstr = raw_val
            state = "msgstr"
            
        elif line.startswith('"'):
            # Multiline continuation
            val = line[1:-1]
            if state == "msgid":
                current_msgid += val
            elif state == "msgstr":
                current_msgstr += val

    # Add last entry
    if current_msgid is not None and current_msgstr is not None:
        if current_msgid != "":
            messages[current_msgid] = current_msgstr

    return header, messages

def update_lang_po(source_strings, outfile):
    """
    Updates a language PO file with new strings from source, preserving existing translations.
    """
    header, existing_messages = parse_po(outfile)
    
    # EXISTING MESSAGES keys are already ESCAPED strings (e.g. "Line 1\\nLine 2")
    # SOURCE STRINGS keys are RAW Python strings (e.g. "Line 1\nLine 2")
    
    # We need to build a map of Existing (Escaped) -> Translation
    # But for comparison, we need to compare apples to apples.
    
    # Let's normalize everything to the ESCAPED format for keying.
    
    normalized_existing = {}
    for k, v in existing_messages.items():
        # k is already the escaped string found in the file (e.g. "Foo\\tBar")
        normalized_existing[k] = v

    print(f"Source strings: {len(source_strings)}")
    print(f"Existing messages in {outfile}: {len(existing_messages)}")
    
    merged_messages = normalized_existing.copy()
    added_count = 0
    
    for s in source_strings.keys():
        # s is the Raw string. Escape it to match PO format.
        # We need to replicate default Python string representation for consistency with what we read back?
        # Or standard PO escaping: \ -> \\, " -> \", \n -> \n, \t -> \t
        esc_s = s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\t', '\\t')
        
        if esc_s not in merged_messages:
            merged_messages[esc_s] = ""
            added_count += 1
        elif merged_messages[esc_s] == "" or "fuzzy" in merged_messages[esc_s]: # Optional: if we want to update fuzzy or empty?
            pass

    print(f"Added {added_count} new strings.")
    
    # Write back
    timestamp = time.strftime('%Y-%m-%d %H:%M%z')
    if not header:
        content = f"""# A11YTube Translation
# Generated by update_po.py
#
msgid ""
msgstr ""
"Project-Id-Version: A11YTube 0.2.5\\n"
"Report-Msgid-Bugs-To: \\n"
"POT-Creation-Date: {timestamp}\\n"
"PO-Revision-Date: {timestamp}\\n"
"Last-Translator: Full Name <email@example.com>\\n"
"Language-Team: \\n"
"Language: \\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"X-Generator: Python Script\\n"

"""
    else:
        # Reconstruct header block
        content = ""
        for h in header:
            content += h + "\n"
        if not any("msgid" in h for h in header): # Verify if we captured the main header msgid "" block
             # If our parser skipped the internal metadata of the header, we might need to add it or it's implicitly in 'header' list if we changed parser logic.
             # My new parser logic stores comments in 'header', but the 'msgid ""' block is skipped.
             # We should probably hardcode the standard header block or try to preserve the metadata from the file if possible.
             # For now, let's append the standard metadata block immediately after comments.
             pass
        
        # Actually my new parser puts comments in 'header'. It consumes 'msgid ""' to switch state.
        # So 'header' variable only has comments.
        # We need to write the msgid "" block.
        
        content += 'msgid ""\n'
        content += 'msgstr ""\n'
        content += f'"Project-Id-Version: A11YTube 0.2.5\\n"\n'
        content += f'"Report-Msgid-Bugs-To: \\n"\n'
        content += f'"POT-Creation-Date: {timestamp}\\n"\n'
        content += f'"PO-Revision-Date: {timestamp}\\n"\n'
        content += f'"Last-Translator: Full Name <email@example.com>\\n"\n'
        content += f'"Language-Team: \\n"\n'
        content += f'"Language: vi\\n"\n'
        content += f'"MIME-Version: 1.0\\n"\n'
        content += f'"Content-Type: text/plain; charset=UTF-8\\n"\n'
        content += f'"Content-Transfer-Encoding: 8bit\\n"\n'
        content += f'"X-Generator: Python Script\\n"\n\n'

    for s_key in sorted(merged_messages.keys()):
        # s_key is the escaped string.
        # Check source locations. We need to match with RAW string.
        # Reverse escape is tricky if not perfect.
        # But for 'source_strings' lookup we need the exact raw string key.
        
        # Try to find the matching raw string in source_strings
        found_src = False
        for raw_s in source_strings.keys():
            # Escape it again to compare
            check_esc = raw_s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\t', '\\t')
            if check_esc == s_key:
                locs = source_strings[raw_s]
                for path, line in locs:
                    content += f"#: {path}:{line}\n"
                found_src = True
                break
        
        content += f'msgid "{s_key}"\n'
        content += f'msgstr "{merged_messages[s_key]}"\n\n'

    os.makedirs(os.path.dirname(outfile), exist_ok=True)
    with open(outfile, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Updated {outfile}: {len(merged_messages)} strings")

if __name__ == "__main__":
    root = os.path.join(os.getcwd(), "source")
    
    # Update EN (Template/Source)
    en_outfile = os.path.join(root, "languages", "en", "LC_MESSAGES", "A11YTube.po")
    strings = extract_strings(root)
    write_pot(strings, en_outfile)
    
    # Update VI (Target)
    vi_outfile = os.path.join(root, "languages", "vi", "LC_MESSAGES", "A11YTube.po")
    update_lang_po(strings, vi_outfile)

