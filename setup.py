import pathlib

import setuptools

setuptools.setup(
    name="cypartagraphqlsubscriptionstools",
    version="1.1.0",
    description = "A CypartaGraphqlSubscriptionsTools implementation for Graphene + Django built using Django Channels +reactive programming in python (RxPY) . Provides support for model creation, mutation and deletion,and get data with websocket or path list of events name for subscriptions .",
    long_description=pathlib.Path("README.md").read_text(),
    long_description_content_type="text/markdown",
    url="https://cyparta.com/",
    author="Cyparta Software House",
    author_email="Support@cyparta.com",
    license="LICENSE",
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
    install_requires=["Django==4.2.7","graphene==3.3","reactivex","django_lifecycle"],
    packages=setuptools.find_packages(),
    include_package_data=True,
    
)