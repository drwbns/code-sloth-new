from setuptools import setup, find_packages

setup(
    name="pydantic-agent",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "aiohttp>=3.8.0",
        "pydantic>=2.0.0",
        "python-dotenv>=0.19.0",
        "async-timeout>=4.0.0",
        "asyncio>=3.4.3",
        "rich>=13.7.0",
        "prompt_toolkit>=3.0.43"
    ],
)
