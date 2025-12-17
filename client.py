import hashlib
import subprocess
import uuid
import platform
import requests
import argparse
import sys


def run_cmd(cmd):
    try:
        out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
        return out.strip()
    except Exception:
        return ""


def get_cpu_id():
    if platform.system() == "Windows":
        out = run_cmd("wmic cpu get ProcessorId")
        for line in out.splitlines():
            line = line.strip()
            if line and line.lower() != "processorid":
                return line
    return platform.processor() or ""


def get_disk_serial():
    if platform.system() == "Windows":
        out = run_cmd("wmic diskdrive get SerialNumber")
        for line in out.splitlines():
            line = line.strip()
            if line and not line.lower().startswith("serialnumber"):
                return line
    return ""


def get_mac():
    node = uuid.getnode()
    mac = ':'.join([f"{(node >> ele) & 0xff:02x}" for ele in range(0,8*6,8)][::-1])
    return mac


def make_fingerprint():
    cpu = get_cpu_id()
    disk = get_disk_serial()
    mac = get_mac()

    seed = "|".join([cpu, disk, mac])
    h = hashlib.sha256(seed.encode('utf-8')).hexdigest()
    return h


def verify_with_server(server_url, license_key, fingerprint):
    payload = {
        "license_key": license_key,
        "device_id": fingerprint
    }
    try:
        r = requests.post(server_url.rstrip('/') + '/verify', json=payload, timeout=10)
    except Exception as e:
        print(f"Error contacting server: {e}")
        return False

    if r.status_code == 200:
        print("Verified: OK")
        return True
    else:
        print(f"Verification failed: {r.status_code} {r.text}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Collect machine fingerprint and verify license")
    parser.add_argument('--server', default='http://127.0.0.1:8000', help='License server base URL')
    parser.add_argument('--license', required=True, help='License key to verify')
    args = parser.parse_args()

    fingerprint = make_fingerprint()
    print(f"Fingerprint: {fingerprint}")

    ok = verify_with_server(args.server, args.license, fingerprint)
    if not ok:
        print("Access denied. Exiting.")
        sys.exit(1)


if __name__ == '__main__':
    main()
