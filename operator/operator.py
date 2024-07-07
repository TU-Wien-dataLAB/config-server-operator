import json
import kopf
import kubernetes


@kopf.on.create('configserver')
def create_fn(meta, spec, **kwargs):
    # TODO: also read all Key-Value CRDs and create these for the correct ConfigMap
    client = kubernetes.client.api_client.ApiClient(configuration=kubernetes.config.load_kube_config())
    api = kubernetes.client.CoreV1Api(api_client=client)
    apps_api = kubernetes.client.AppsV1Api(api_client=client)

    name = meta["name"]
    namespace = meta["namespace"]

    configmap_manifest = kubernetes.client.V1ConfigMap(api_version="v1",
                                                       metadata={"name": f"{name}-values", "namespace": namespace},
                                                       data={})
    api.create_namespaced_config_map(namespace, body=configmap_manifest)

    service = kubernetes.client.V1Service(api_version="v1",
                                          metadata={"name": name, "namespace": namespace},
                                          spec={"type": "ClusterIP",
                                                "ports": [
                                                    {"protocol": "TCP", "port": spec["containerPort"],
                                                     "targetPort": spec["containerPort"], "name": "http"}
                                                ],
                                                "selector": {"app": name}})
    api.create_namespaced_service(namespace, body=service)

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
    client = kubernetes.client.api_client.ApiClient(configuration=kubernetes.config.load_kube_config())
    api = kubernetes.client.CoreV1Api(api_client=client)
    apps_api = kubernetes.client.AppsV1Api(api_client=client)

    name = meta["name"]
    namespace = meta["namespace"]

    try:
        apps_api.delete_namespaced_deployment(name, namespace)
    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 404:
            pass

    try:
        api.delete_namespaced_service(name, namespace)
    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 404:
            pass

    try:
        api.delete_namespaced_config_map(f"{name}-values", namespace)
    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 404:
            pass


def _get_config_map(config_name, namespace) -> tuple[kubernetes.client.V1ConfigMap, kubernetes.client.CoreV1Api]:
    client = kubernetes.client.api_client.ApiClient(configuration=kubernetes.config.load_kube_config())
    api = kubernetes.client.CoreV1Api(api_client=client)
    try:
        config_map = api.read_namespaced_config_map(name=f"{config_name}-values", namespace=namespace)
        if config_map.data is None:
            config_map.data = {}
        return config_map, api
    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 404:
            kopf.PermanentError(f"ConfigMap {config_name}-values not found! First create a valid ConfigServer.")


@kopf.on.create('keyvaluepair')
@kopf.on.update('keyvaluepair')
def create_config_fn(meta, spec, **kwargs):
    # TODO: split update and create handlers to check if key already exists in create step
    config_name = spec["config"]
    namespace = meta["namespace"]
    config_map, api = _get_config_map(config_name, namespace)

    # config_map.data has to be of type dict[str, str] so encode values as json string
    config_map.data[spec["key"]] = json.dumps(spec["value"])
    api.patch_namespaced_config_map(name=f"{config_name}-values", namespace=namespace, body=config_map)


@kopf.on.delete('keyvaluepair')
def delete_config_fn(meta, spec, **kwargs):
    config_name = spec["config"]
    namespace = meta["namespace"]
    config_map, api = _get_config_map(config_name, namespace)

    config_map.data.pop(spec["key"], None)
    api.patch_namespaced_config_map(name=f"{config_name}-values", namespace=namespace, body=config_map)
