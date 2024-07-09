
# config-server-operator

![Python Version from PEP 621 TOML](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2FTU-Wien-dataLAB%2Fconfig-server-operator%2Fmain%2Fpyproject.toml)


This operator provides CRDs to create key/value pairs (`KeyValuePair`). The operator combines these configuration objects into a single `ConfigMap` and deploys a REST API that can be used to access the individual values with the corresponding keys.


## Deployment

See [Kopf documentation](https://kopf.readthedocs.io/en/stable/deployment/). The Dockerfile for the deployment is part of this repository.


## Run Locally

The `config-server-operator` can be run locally without writing a whole deployment for it, for example in a local `minikube` cluster.

Clone the project

```bash
  git clone https://github.com/TU-Wien-dataLAB/config-server-operator.git
```

Go to the project directory

```bash
  cd config-server-operator
```

Install dependencies

```bash
  pip install kopf
```

Add the CRDs to the cluster

```bash
  kubectl apply -f opr/crd.yaml
```

Run the operator

```bash
  kopf run opr/operator.py --verbose
```

