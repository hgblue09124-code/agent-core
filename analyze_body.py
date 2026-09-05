#!/usr/bin/env python3
import re

with open('artifact_body.html') as f:
    html = f.read()

scripts = re.findall(r'<script>(.*?)</script>', html, re.DOTALL)
print("Found", len(scripts), "script tags in body.")
for i, s in enumerate(scripts):
    print(f"\n--- SCRIPT {i} ---")
    print(s)

# Find top level elements / views / screens
print("\n--- HTML DOM STRUCTURE ---")
lines = html.split('\n')
for line in lines:
    if '<div' in line or '<nav' in line or '<main' in line or '<header' in line or 'data-' in line or 'id=' in line:
        if any(keyword in line for keyword in ['app', 'screen', 'tab', 'view', 'nav', 'orb', 'status', 'card', 'header', 'footer', 'state']):
            print(line[:120])
