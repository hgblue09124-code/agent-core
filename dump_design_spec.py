#!/usr/bin/env python3

with open('artifact_source_code.txt') as f:
    text = f.read()

# Extract the style block
import re
styles = re.findall(r'<style>(.*?)</style>', text, re.DOTALL)
if styles:
    with open('artifact_styles.css', 'w') as f:
        f.write(styles[0])
    print("Saved artifact_styles.css (length: {})".format(len(styles[0])))

# Extract text content / HTML structure
body_match = re.search(r'<body[^>]*>(.*?)</body>', text, re.DOTALL)
if body_match:
    body_text = body_match.group(1)
    with open('artifact_body.html', 'w') as f:
        f.write(body_text)
    print("Saved artifact_body.html")
