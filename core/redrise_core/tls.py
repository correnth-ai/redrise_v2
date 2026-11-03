"""Self-signed host certificate (P05-D5). Stations pin its SHA-256 from the
join code; there is no trust-on-first-use. The private key is written to the
host data folder (never to the binary folder) with the user's default ACL."""

from __future__ import annotations

import datetime
import hashlib
import ipaddress
import socket
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


def ensure_cert(dir_: Path, hostnames: list[str] | None = None) -> tuple[Path, Path, str]:
    dir_.mkdir(parents=True, exist_ok=True)
    cert, key = dir_ / "host-cert.pem", dir_ / "host-key.pem"
    if not cert.is_file() or not key.is_file():
        k = ec.generate_private_key(ec.SECP256R1())
        names = hostnames or [socket.gethostname()]
        san: list[x509.GeneralName] = [x509.DNSName(n) for n in names] + [x509.DNSName("localhost"),
                                                                          x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"RedRise team host {names[0]}")])
        now = datetime.datetime.now(datetime.timezone.utc)
        c = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(k.public_key())
             .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=5))
             .not_valid_after(now + datetime.timedelta(days=3650))
             .add_extension(x509.SubjectAlternativeName(san), critical=False)
             .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
             .sign(k, hashes.SHA256()))
        key.write_bytes(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                        serialization.NoEncryption()))
        cert.write_bytes(c.public_bytes(serialization.Encoding.PEM))
    return cert, key, fingerprint(cert)


def fingerprint(cert_pem: Path) -> str:
    c = x509.load_pem_x509_certificate(cert_pem.read_bytes())
    return hashlib.sha256(c.public_bytes(serialization.Encoding.DER)).hexdigest()


def join_code(host: str, port: int, fp: str) -> str:
    return f"rr1:{host}:{port}:{fp}"


def parse_join_code(code: str) -> tuple[str, int, str]:
    parts = (code or "").strip().split(":")
    if len(parts) != 4 or parts[0] != "rr1" or not parts[2].isdigit() or len(parts[3]) != 64:
        raise ValueError("invalid connection code")
    return parts[1], int(parts[2]), parts[3].lower()
