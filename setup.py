import pathlib

import setuptools

setuptools.setup(
    name="cypartagraphqlsubscriptionstools",
    version="4.1.6",
    description = "Graphene + Django GraphQL subscriptions over Django Channels (async WebSockets, bounded outbox, multi-operation registry).",
    long_description=pathlib.Path("README.md").read_text(),
    long_description_content_type="text/markdown",
    url="https://cyparta.com/",
    author="Cyparta Software House",
    author_email="Support@cyparta.com",
    license="MIT",
    project_urls={
        "homepage" : "https://cyparta.com/",
        "Documentation":"https://github.com/Cyparta/CypartaGraphqlSubscriptionsTools",
        "Source":"https://github.com/Cyparta/CypartaGraphqlSubscriptionsTools",
    },
    classifiers = [
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python",
    "Programming Language :: Python :: 3",
],
    python_requires = ">=3.9",
    install_requires=[
        "Django==4.2.7",
        "graphene==3.3",
        "graphene-django>=3.1",
        "channels",
        "django_lifecycle",
    ],
    packages=[
        "CypartaGraphqlSubscriptionsTools",
        "CypartaGraphqlSubscriptionsTools.migrations",
    ],
    include_package_data=True,
    extras_require={
        "test": [
            "pytest>=7.0",
            "pytest-asyncio>=0.21",
            "pytest-django>=4.5",
            "djangorestframework>=3.14",
        ],
    },
)