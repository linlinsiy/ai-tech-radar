#!/usr/bin/env python3
"""
AI技术趋势雷达 - 打包工具

将 AWS 侧服务和内部应用节点分别打包为 tar.gz 归档文件，便于部署到 Linux 服务器。
部署目录：/app/001804/aws 和 /app/001804/internal
"""

import os
import sys
import tarfile
import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
IGNORE_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".git",
    ".gitignore",
    ".idea",
    "*.swp",
    "*.swo",
    ".DS_Store",
    "venv",
    "env",
    "*.egg-info",
    "dist",
    "build",
    "*.log",
    "temp/",
    "temp_*.py",
]


def should_ignore(path: str) -> bool:
    for pattern in IGNORE_PATTERNS:
        if pattern.startswith("*."):
            if path.endswith(pattern[1:]):
                return True
        elif pattern.endswith("/"):
            if path.endswith(pattern) or path == pattern[:-1]:
                return True
        else:
            if pattern in path.split(os.sep):
                return True
    return False


def create_tarball(source_dir: Path, output_path: Path):
    print(f"Packaging {source_dir.name}...")
    
    with tarfile.open(output_path, "w:gz") as tar:
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if not should_ignore(os.path.join(root, d))]
            
            for file in files:
                file_path = os.path.join(root, file)
                if should_ignore(file_path):
                    continue
                
                arcname = os.path.relpath(file_path, BASE_DIR)
                tar.add(file_path, arcname=arcname)
                print(f"  Added: {arcname}")
    
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Created: {output_path} ({size_mb:.2f} MB)\n")


def main():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    aws_source = BASE_DIR / "aws"
    internal_source = BASE_DIR / "internal"
    
    aws_output = BASE_DIR / f"ai-radar-aws-{timestamp}.tar.gz"
    internal_output = BASE_DIR / f"ai-radar-internal-{timestamp}.tar.gz"
    
    if aws_source.exists():
        create_tarball(aws_source, aws_output)
    else:
        print(f"Warning: {aws_source} not found, skipping AWS package")
    
    if internal_source.exists():
        create_tarball(internal_source, internal_output)
    else:
        print(f"Warning: {internal_source} not found, skipping internal package")
    
    print("Packaging completed!")
    print(f"AWS package: {aws_output}")
    print(f"Internal package: {internal_output}")
    print("\nTo deploy as appadmin user:")
    print("  scp ai-radar-aws-*.tar.gz appadmin@server:/app/001804/")
    print("  scp ai-radar-internal-*.tar.gz appadmin@server:/app/001804/")
    print("  ssh appadmin@server")
    print("  cd /app/001804 && tar -xzf ai-radar-aws-*.tar.gz")
    print("  cd /app/001804 && tar -xzf ai-radar-internal-*.tar.gz")
    print("  cd aws && ./deploy/install.sh && ./deploy/start.sh")
    print("  cd internal && ./deploy/install.sh && ./deploy/start.sh")


if __name__ == "__main__":
    main()