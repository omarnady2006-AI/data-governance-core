# 1️⃣ Environment Check
import os
import sys
import subprocess
import traceback
import pandas as pd
from leakage_agent import LeakageValidator
from leakage_agent.batch_processor import BatchProcessor

print(sys.version)
print(sys.executable)
print('deps ok')
print('pandas', pd.__version__)

# 2️⃣ Unit Tests
# Task B: Run unit tests
print("Running Task B: Unit tests...")
env = os.environ.copy()
env["PYTHONPATH"] = os.path.abspath("leakage_agent/src")

# Ensure outputs directory exists
if not os.path.exists("outputs"):
    os.makedirs("outputs")

cmd = [sys.executable, "-m", "pytest", "-q", "leakage_agent/tests"]
result = subprocess.run(cmd, env=env, capture_output=True, text=True)

print(result.stdout)
print(result.stderr)

with open("outputs/test_report_unit.txt", "w") as f:
    f.write(result.stdout)
    f.write(result.stderr)

if result.returncode != 0:
    print(f"Tests failed with exit code {result.returncode}")
    sys.exit(result.returncode)
else:
    print("Tests passed.")

# 3️⃣ Smoke Tests
# Task D: Run API smoke test
print("Running Task D: API smoke test...")
sys.path.insert(0, os.path.abspath("leakage_agent/src"))

try:
    v = LeakageValidator()  # should auto-resolve policy_dir
    df = pd.DataFrame({"email":["alice@example.com"],"label":["cat"],"amount":[100]})
    res = v.validate(df, copy_id="smoke_api_001")
    print("decision:", res.decision)
    print("reason_codes:", getattr(res, "reason_codes", None))
    print("metrics keys:", list(getattr(res, "metrics", {}).keys())[:10])
except Exception as e:
    print(f"API Smoke test failed: {e}")
    traceback.print_exc()
    sys.exit(1)

# CLI Smoke Test
# Task E: Run CLI smoke test
print("Running Task E: CLI smoke test...")
env = os.environ.copy()
env["PYTHONPATH"] = os.path.abspath("leakage_agent/src")

# Create tmp_smoke directory
tmp_dir = "tmp_smoke"
if not os.path.exists(tmp_dir):
    os.makedirs(tmp_dir)

# Create ok.csv
with open(os.path.join(tmp_dir, "ok.csv"), "w") as f:
    f.write("email,label,amount\nalice@example.com,cat,100")

# Run CLI for ok.csv
print("Testing ok.csv...")
cmd_ok = [sys.executable, "-m", "leakage_agent.cli", "run", "--input", os.path.join(tmp_dir, "ok.csv"), "--copy-id", "smoke_cli_ok"]
res_ok = subprocess.run(cmd_ok, env=env, capture_output=True, text=True)
print(res_ok.stdout)
print(res_ok.stderr)
print(f"EXIT={res_ok.returncode}")

# Create secret.csv
with open(os.path.join(tmp_dir, "secret.csv"), "w") as f:
    f.write("secret_key,label\nmy-secret-token,dog")

# Run CLI for secret.csv
print("\nTesting secret.csv...")
cmd_secret = [sys.executable, "-m", "leakage_agent.cli", "run", "--input", os.path.join(tmp_dir, "secret.csv"), "--copy-id", "smoke_cli_secret"]
res_secret = subprocess.run(cmd_secret, env=env, capture_output=True, text=True)
print(res_secret.stdout)
print(res_secret.stderr)
print(f"EXIT={res_secret.returncode}")

# Batch Processing Test
if __name__ == '__main__':
    # Task F: Run batch processing smoke test
    print("Running Task F: Batch processing smoke test...")
    sys.path.insert(0, os.path.abspath("leakage_agent/src"))

    # Create example directory and files if they don't exist
    example_dir = "transform/examples"
    if not os.path.exists(example_dir):
        os.makedirs(example_dir)

    with open(os.path.join(example_dir, "batch1.csv"), "w") as f:
        f.write("email,label\nbob@example.com,bird")
    with open(os.path.join(example_dir, "batch2.csv"), "w") as f:
        f.write("secret_key,label\nmy-batch-secret,fish")

    try:
        p = BatchProcessor(verbose=False)
        results = p.process_directory(example_dir)
        print(results)
    except Exception as e:
        print(f"Batch processing smoke test failed: {e}")
        traceback.print_exc()
        sys.exit(1)


# Check Policy Dir
sys.path.insert(0, os.path.abspath("leakage_agent/src"))
v = LeakageValidator()
print(f"validator.policy_dir={v.policy_dir}")
if hasattr(v.pipeline, 'policy_dir'):
    print(f"pipeline.policy_dir={v.pipeline.policy_dir}")
else:
    print("pipeline.policy_dir=MISSING")
