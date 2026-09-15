import json
import re
import urllib.request

def extract_json_after_key(html, key):
    idx = html.find(key)
    if idx < 0:
        return None
    start = html.find("[", idx) if html[idx:].lstrip().startswith(key + ":") and "[" in html[idx:idx+20] else html.find("{", idx)
    if start < 0:
        return None
    open_ch, close_ch = ("[", "]") if html[start] == "[" else ("{", "}")
    depth = 0
    for i, ch in enumerate(html[start:], start):
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return json.loads(html[start : i + 1])
    return None

html = urllib.request.urlopen("https://tarot.run/zh/library/cards/the-empress").read().decode("utf-8")
# dump keys near card content
for key in ["upright", "reversed", "keywords", "description", "love", "career", "advice"]:
    print(key, html.count(key))

# extract any large JSON blobs with card fields
for m in re.finditer(r'\{"id":"[^"]+","slug":"[^"]+","name"', html):
    start = m.start()
    depth = 0
    for i, ch in enumerate(html[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                obj = json.loads(html[start : i + 1])
                print(json.dumps(obj, ensure_ascii=False, indent=2)[:5000])
                break
    break
