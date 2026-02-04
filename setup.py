from setuptools import setup, find_packages

setup(
    name="moltbot",
    version="0.1.0",
    description="A high-performance distributed LLM calling framework",
    author="Your Name",
    author_email="you@example.com",
    url="https://github.com/987630959/moltbotRepository",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        "redis>=5.0.0",
        "aio-pika>=9.3.0",
        "httpx>=0.25.0",
        "asyncio-throttle>=1.0.2",
        "orjson>=3.9.0",
        "tenacity>=8.2.0",
        "python-dotenv>=1.0.0",
        "structlog>=24.0.0",
        "uvicorn>=0.25.0",
        "fastapi>=0.109.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.23.0",
            "black>=23.0.0",
            "ruff>=0.1.0",
            "mypy>=1.7.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "moltbot=main:main",
        ]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
