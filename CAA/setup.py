from setuptools import setup, find_packages

setup(
    name="caa",
    version="1.0.0",
    description="CFM AntiFraud Analyzer",
    author="CAA Team",
    packages=find_packages(),
    install_requires=[
        "aiohttp>=3.8.0",
        "websockets>=10.0",
        "pillow>=9.0.0",
        "numpy>=1.21.0",
        "pandas>=1.3.0",
        "matplotlib>=3.4.0",
        "seaborn>=0.11.0",
        "colorama>=0.4.4",
        "jsonschema>=4.0.0",
        "requests>=2.26.0",
        "beautifulsoup4>=4.10.0",
        "lxml>=4.6.0",
        "pytest>=6.2.0"
    ],
    entry_points={
        "console_scripts": [
            "caa-scan=scripts.run_scan:main",
            "caa-batch=scripts.batch_scan:main",
            "caa-compare=scripts.compare_profiles:main",
        ]
    },
    python_requires=">=3.8",
)