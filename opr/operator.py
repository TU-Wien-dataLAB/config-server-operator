import json
import logging

import kopf
import kubernetes
from kubernetes.client import ApiClient, CoreV1Api, AppsV1Api, CustomObjectsApi, V1ConfigMap, V1Service


@kopf.on.create('configserver')
def create_fn(meta, spec, **kwargs):
    client = ApiClient(configuration=kubernetes.config.load_incluster_config())
    api = CoreV1Api(api_client=client)
    apps_api = AppsV1Api(api_client=client)
    crd_api = CustomObjectsApi(api_client=client)

    name = meta["name"]
    namespace = meta["namespace"]

    # Read all existing Key/Value pairs and add them to the ConfigMap data
    cfg_map_data = dict()
    kv_pairs = crd_api.list_namespaced_custom_object("datalab.tuwien.ac.at", "v1", namespace, "keyvaluepairs")
    kv_specs = map(lambda kvp: kvp["spec"], kv_pairs["items"])
    for kv_spec in kv_specs:
        if kv_spec["config"] == name:
            cfg_map_data[kv_spec["key"]] = json.dumps(kv_spec["value"])

    # Create the ConfigMap
    configmap_manifest = V1ConfigMap(api_version="v1",
                                     metadata={"name": f"{name}-values", "namespace": namespace},
                                     data=cfg_map_data)
    api.create_namespaced_config_map(namespace, body=configmap_manifest)

    # Create the service for the deployment
    service = V1Service(api_version="v1",
                        metadata={"name": name, "namespace": namespace},
                        spec={"type": "ClusterIP",
                              "ports": [
                                  {"protocol": "TCP", "port": spec["containerPort"],
                                   "targetPort": spec["containerPort"], "name": "http"}
                              ],
                              "selector": {"app": name}})
    api.create_namespaced_service(namespace, body=service)

    # Create the deployment
    server_deployment_manifest = {
        "kind": "Deployment",
        "apiVersion": "apps/v1",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": {
                "app": name
            }
        },
        "spec": {
            "replicas": 1,
            "selector": {
                "matchLabels": {
                    "app": name
                }
            },
            "template": {
                "metadata": {
                    "labels": {
                        "app": name
                    }
                },
                "spec": {
                    "containers": [{
                        "name": name,
                        "image": spec["image"],
                        "imagePullPolicy": spec["imagePullPolicy"],
                        "ports": [{
                            "name": "http",
                            "containerPort": spec["containerPort"],
                            "protocol": "TCP",
                        }],
                        "env": [
                            {"name": "CONFIG_SERVER_DIR", "value": spec["configMountPath"]},
                            {"name": "CONFIG_SERVER_PORT", "value": str(spec["containerPort"])},
                        ],
                        "volumeMounts": [{
                            "name": "config",
                            "mountPath": spec["configMountPath"],
                        }]
                    }],
                    "volumes": [{
                        "name": "config",
                        "configMap": {
                            "defaultMode": 444,
                            "name": f"{name}-values",
                        }
                    }]
                }
            }
        }
    }
    apps_api.create_namespaced_deployment(namespace, body=server_deployment_manifest)


@kopf.on.delete('configserver')
def delete_fn(meta, spec, **kwargs):
    client = ApiClient(configuration=kubernetes.config.load_incluster_config())
    api = CoreV1Api(api_client=client)
    apps_api = AppsV1Api(api_client=client)

    name = meta["name"]
    namespace = meta["namespace"]

    delete_calls = [lambda: apps_api.delete_namespaced_deployment(name, namespace),
                    lambda: api.delete_namespaced_service(name, namespace),
                    lambda: api.delete_namespaced_config_map(f"{name}-values", namespace)]

    for func in delete_calls:
        try:
            func()
        except kubernetes.client.exceptions.ApiException as e:
            if e.status == 404:
                continue  # ignore resources that have already been deleted
            else:
                raise kopf.PermanentError(f"Failed to delete config server {name}: {e.reason}")


def _get_config_map(config_name: str, namespace: str, logger: logging.Logger) -> tuple[V1ConfigMap | None, CoreV1Api]:
    client = kubernetes.client.api_client.ApiClient(configuration=kubernetes.config.load_kube_config())
    api = kubernetes.client.CoreV1Api(api_client=client)
    try:
        config_map = api.read_namespaced_config_map(name=f"{config_name}-values", namespace=namespace)
        if config_map.data is None:
            config_map.data = {}
        return config_map, api
    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 404:
            logger.warning(
                f"Config '{config_name}' not found! Key/Value pair will be added once a valid ConfigServer is created.")
            return None, api
        else:
            raise kopf.PermanentError(f"Failed to load config values '{config_name}': {e.reason}")


@kopf.on.create('keyvaluepair')
@kopf.on.update('keyvaluepair')
def create_config_fn(meta, spec, logger, **kwargs):
    # TODO: split update and create handlers to check if key already exists in create step
    config_name = spec["config"]
    namespace = meta["namespace"]
    config_map, api = _get_config_map(config_name, namespace, logger)

    # config_map.data has to be of type dict[str, str] so encode values as json string
    if config_map is not None:
        config_map.data[spec["key"]] = json.dumps(spec["value"])
        api.patch_namespaced_config_map(name=f"{config_name}-values", namespace=namespace, body=config_map)


@kopf.on.delete('keyvaluepair')
def delete_config_fn(meta, spec, logger, **kwargs):
    config_name = spec["config"]
    namespace = meta["namespace"]
    config_map, api = _get_config_map(config_name, namespace, logger)

    if config_map is not None:
        config_map.data.pop(spec["key"], None)
        api.patch_namespaced_config_map(name=f"{config_name}-values", namespace=namespace, body=config_map)
