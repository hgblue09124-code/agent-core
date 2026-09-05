#!/usr/bin/env python3
import re

with open('artifact_source_code.txt') as f:
    text = f.read()

print("================ DESIGN TOKENS ================")
tokens = re.findall(r'--[a-zA-Z0-9-]+:[^;]+;', text)
for t in tokens:
    print(t)

print("\n================ SCREENS & LABELS ================")
screen_labels = re.findall(r'<div class="screen-label">(.*?)</div>\s*</div>', text, re.DOTALL)
for sl in screen_labels:
    print("----------------")
    print(sl.strip())

print("\n================ 9 STATES ================")
state_cards = re.findall(r'<div class="state-card">(.*?)</div>\s*</div>\s*</div>', text, re.DOTALL)
print("Found state cards:", len(state_cards))
for i, sc in enumerate(state_cards):
    print(f"\n--- STATE {i+1} ---")
    lines = [line.strip() for line in sc.split('\n') if line.strip()]
    print("\n".join(lines[:15]))
