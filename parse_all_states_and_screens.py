#!/usr/bin/env python3
import re

with open('artifact_source_code.txt') as f:
    code = f.read()

# Print CSS rules
print("=== CSS STYLES PREVIEW ===")
style_match = re.search(r'<style>(.*?)</style>', code, re.DOTALL)
if style_match:
    style_text = style_match.group(1)
    for line in style_text.split('\n'):
        if line.strip().startswith('.') or line.strip().startswith(':root') or line.strip().startswith('@keyframes'):
            print(line[:80])

# Parse all 9 states explicitly from HTML
print("\n=== ALL 9 INTERACTION STATES ===")
state_matches = re.findall(r'<div class="state-card">(.*?)</div>\s*</div>', code, re.DOTALL)
print(f"Total state card blocks found: {len(state_matches)}")

# Let's search tags in states grid
grid_match = re.search(r'<div class="states-grid">(.*?)</div>\s*</div>\s*</div>\s*</section>', code, re.DOTALL)
if grid_match:
    tags = re.findall(r'<div class="tag">(.*?)</div>', grid_match.group(1))
    print("State Tags found:", tags)
    print("Count of tags:", len(tags))

# Let's search all screen DOM content
print("\n=== ALL SCREENS ===")
screen_blocks = re.findall(r'<div class="screen-block">(.*?)<div class="screen-label">', code, re.DOTALL)
print("Screen blocks found:", len(screen_blocks))

for i, sb in enumerate(screen_blocks):
    print(f"\n================ SCREEN {i+1} ================")
    print(sb[:1500])
