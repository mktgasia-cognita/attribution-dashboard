import json

with open("/tmp/sa-key.json") as f:
    sa = json.load(f)

lines = ['[gcp_service_account]']
for k, v in sa.items():
    if "\n" in v:
        v = v.replace("\n", "\\n")
    lines.append(f'{k} = "{v}"')

out = "/tmp/sa-key-toml.txt"
with open(out, "w") as f:
    f.write("\n".join(lines) + "\n")
print(f"Written to {out}")
