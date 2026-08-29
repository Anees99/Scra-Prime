from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="stealthflow",
    version="1.0.0",
    author="StealthFlow Team",
    description="Enterprise-grade web scraping package with 3-tiered WAF bypass architecture",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/stealthflow/stealthflow",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "curl_cffi>=0.6.0",
        "scrapling>=0.1.0",
        "camoufox>=0.3.0",
        "aiohttp>=3.9.0",
        "pydantic>=2.0.0",
        "asyncio>=3.4.3",
    ],
    extras_require={
        "geoip": ["camoufox[geoip]"],
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "stealthflow=stealthflow.fetcher:main",
        ],
    },
)
