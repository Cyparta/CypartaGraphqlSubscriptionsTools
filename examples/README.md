# Examples

These folders are **not** part of the published wheel (see `setup.py` `find_packages` excludes). They show how to wire **CypartaGraphqlSubscriptionsTools** in a real Django project.

- **`basic_django_app`** — demo `MyModel` + Graphene subscription schema (moved out of the core package in v4.1+).

To try locally (from a **git checkout**, not from the PyPI wheel), add to **`INSTALLED_APPS`**:

```python
"examples.basic_django_app.apps.BasicDjangoAppConfig",
```

Set **`GRAPHENE["SCHEMA"] = "examples.basic_django_app.schema.schema"`**, run **`manage.py migrate`**, then use your Channels routing with **`CypartaGraphqlSubscriptionsConsumer`** as in the main README.
