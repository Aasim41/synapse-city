import re

with open('frontend/src/app/page.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'className=\"f-ew (.*?)\"(\s+style={{.*?\'flowEast.*?)', r'className="f-ew dir-east \1"\2', content)
content = re.sub(r'className=\"f-ew (.*?)\"(\s+style={{.*?\'flowWest.*?)', r'className="f-ew dir-west \1"\2', content)
content = re.sub(r'className=\"f-ns (.*?)\"(\s+style={{.*?\'flowSouth.*?)', r'className="f-ns dir-south \1"\2', content)
content = re.sub(r'className=\"f-ns (.*?)\"(\s+style={{.*?\'flowNorth.*?)', r'className="f-ns dir-north \1"\2', content)

with open('frontend/src/app/page.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
