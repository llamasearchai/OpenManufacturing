from setuptools import setup, find_packages

setup(
    name="openmanufacturing",
    version="1.0.0",
    description="Advanced optical packaging and assembly platform",
    author="LlamaSearch AI",
    author_email="info@llamasearch.ai",
    url="https://github.com/llamasearchai/OpenManufacturing",
    packages=find_packages(include=["openmanufacturing", "openmanufacturing.*"]),
    include_package_data=True,
    package_data={
        "openmanufacturing": ["py.typed", "ui/dist/*", "ui/dist/**/*"],
        "": ["*.json", "*.yaml", "*.yml", "*.html", "*.css", "*.js"],
    },
    install_requires=[
        "fastapi>=0.115.0",
        "uvicorn>=0.34.0",
        "pydantic>=2.11.0",
        "sqlalchemy>=2.0.0",
        "passlib>=1.7.4",
        "python-jose>=3.3.0",
        "python-multipart>=0.0.6",
        "aiosmtplib>=4.0.0",
        "redis>=6.0.0",
        "pyjwt>=2.10.0",
        "httpx>=0.28.0",
        "psycopg2-binary>=2.9.9",
        "prometheus-client>=0.19.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.3.0",
            "pytest-asyncio>=0.26.0",
            "pytest-cov>=4.1.0",
            "black>=23.3.0",
            "mypy>=1.9.0",
            "ruff>=0.1.0",
        ],
    },
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    entry_points={
        "console_scripts": [
            "openmanufacturing_cli=openmanufacturing.cli:main",
        ],
    },
)
