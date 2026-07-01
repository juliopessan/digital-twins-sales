import json
from pathlib import Path

# Verify nubank.json
nubank_path = Path('accounts/nubank.json')
with open(nubank_path, encoding='utf-8') as f:
    data = json.load(f)
    if isinstance(data, dict):
        print(f"✓ nubank.json is VALID (account_name={data.get('account_name')})")
    else:
        print(f"✗ nubank.json is INVALID ({type(data).__name__})")

# Verify magazine-luiza.json
magalu_path = Path('accounts/magazine-luiza.json')
if magalu_path.exists():
    with open(magalu_path, encoding='utf-8') as f:
        data = json.load(f)
        if isinstance(data, dict):
            print(f"✓ magazine-luiza.json is VALID (account_name={data.get('account_name')})")
        else:
            print(f"✗ magazine-luiza.json is INVALID ({type(data).__name__})")
else:
    print("✗ magazine-luiza.json does NOT exist")
