from __future__ import annotations

import ssl
import subprocess
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parent


def cert_dir() -> Path:
    path = project_root() / "data" / "certs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def dev_cert_paths() -> tuple[Path, Path]:
    root = cert_dir()
    return root / "dev-cert.pem", root / "dev-key.pem"


def ensure_dev_certificates() -> tuple[Path, Path]:
    cert_path, key_path = dev_cert_paths()
    if cert_path.exists() and key_path.exists():
        return cert_path, key_path

    for path in (cert_path, key_path):
        if path.exists():
            path.unlink()

    command = [
        "openssl",
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-sha256",
        "-days",
        "365",
        "-nodes",
        "-keyout",
        str(key_path),
        "-out",
        str(cert_path),
        "-subj",
        "/CN=localhost",
        "-addext",
        "subjectAltName=DNS:localhost,IP:127.0.0.1",
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return cert_path, key_path


def build_server_ssl_context() -> ssl.SSLContext:
    cert_path, key_path = ensure_dev_certificates()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    return context


def build_client_ssl_context() -> ssl.SSLContext:
    cert_path, _ = ensure_dev_certificates()
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(cert_path))
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context
