#!/usr/bin/env python3
import re

with open('artifact_source_code.txt') as f:
    code = f.read()

print("File size:", len(code))

# Extract CSS Variables / Design Tokens
print("\n=== DESIGN TOKENS (:root) ===")
root_match = re.search(r':root\s*\{([^}]+)\}', code)
if root_match:
    for line in root_match.group(1).strip().split('\n'):
        if line.strip():
            print("  ", line.strip())

# Extract Screens / Tabs
print("\n=== SCREENS / NAVIGATION ===")
screens = re.findall(r'id=["\']screen-([^"\']+)["\']', code)
print("Screens found:", screens)

tabs = re.findall(r'data-tab=["\']([^"\']+)["\']', code)
print("Tabs found:", set(tabs))

# Extract Component / Element IDs
print("\n=== INTERACTION STATES / BUTTONS / COMPONENTS ===")
ids = re.findall(r'id=["\']([^"\']+)["\']', code)
print("Element IDs:", ids)

# Print JS script logic summary
print("\n=== JAVASCRIPT LOGIC SUMMARY ===")
scripts = re.findall(r'<script>(.*?)</script>', code, re.DOTALL)
for s in scripts:
    print(s[:1000])
