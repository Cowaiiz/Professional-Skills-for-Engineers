"""Create a local account for the optional Home IoT password gate."""
import argparse
import getpass
import json
import secrets
from pathlib import Path

from backend.access import password_hash
from common.config import ROOT


def write_account(path, username, password):
    salt = secrets.token_bytes(16)
    record = {'username': username, 'salt': salt.hex(), 'digest': password_hash(password, salt).hex()}
    Path(path).write_text(json.dumps(record) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--username', default='demo')
    args = parser.parse_args()
    username = args.username.strip()
    password = getpass.getpass('Choose a password (14 or more characters): ')
    if not 0 < len(username) <= 64 or not 14 <= len(password) <= 256:
        parser.error('Use a username of 1–64 characters and a password of 14–256 characters.')
    if getpass.getpass('Confirm password: ') != password:
        parser.error('Passwords did not match.')
    write_account(ROOT / 'auth.local.json', username, password)
    print('Demo login saved locally. Restart the demo to enable it.')


if __name__ == '__main__':
    main()
