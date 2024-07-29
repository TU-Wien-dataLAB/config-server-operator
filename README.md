
# config-server-operator

![Python Version from PEP 621 TOML](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2FTU-Wien-dataLAB%2Fconfig-server-operator%2Fmain%2Fpyproject.toml)


This operator provides CRDs to create key/value pairs (`KeyValuePair`). The operator combines these configuration objects into a single `ConfigMap` and deploys a REST API that can be used to access the individual values with the corresponding keys.

The operator is written in the [Kubernetes Operators Framework (Kopf)](https://kopf.readthedocs.io/en/stable/index.html#) while the HTTP server for the REST API is written in [Tornado](https://www.tornadoweb.org/en/stable/). The code for the operator is found in the `/opr` directory while the code for the Tornado server is located in the `/srv` directory.

The `/tests` directory contains unit and integration tests for the server and operator. The `/examples` directory contains simple examples on how to use the custom resources to deploy a config server instance. The `/chart` directory contains the definitions for a [Helm](https://helm.sh/) chart.

## Deployment

See [Kopf documentation](https://kopf.readthedocs.io/en/stable/deployment/). The Dockerfile for the deployment is part of this repository.

This repository also contains a Helm chart which can be deployed with:

```bash
  TODO: how?
```

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

