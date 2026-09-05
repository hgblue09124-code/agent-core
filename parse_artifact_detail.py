#!/usr/bin/env python3

with open('artifact_source_code.txt') as f:
    code = f.read()

# Let's inspect the HTML body structure
body_start = code.find('<body')
body_end = code.find('</body>')
if body_start != -1 and body_end != -1:
    body_content = code[body_start:body_end+7]
    with open('artifact_body.html', 'w') as f:
        f.write(body_content)
    print("Saved artifact_body.html (length: {})".format(len(body_content)))

# Let's extract script tags
import re
scripts = re.findall(r'<script>(.*?)</script>', code, re.DOTALL)
for i, s in enumerate(scripts):
    with open(f'artifact_script_{i}.js', 'w') as f:
        f.write(s)
    print(f"Saved artifact_script_{i}.js (length: {len(s)})")
