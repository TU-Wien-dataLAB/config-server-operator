import kopf
import kubernetes


@kopf.on.create('configserver')
def create_fn(meta, spec, memo: kopf.Memo, **kwargs):
    client = kubernetes.client.api_client.ApiClient(configuration=kubernetes.config.load_kube_config())
    api = kubernetes.client.CoreV1Api(api_client=client)
    apps_api = kubernetes.client.AppsV1Api(api_client=client)

    name = meta["name"]
    namespace = meta["namespace"]

    # TODO: remove memo if not used in handlers
    memo.config_name = name
    memo.namespace = namespace

    configmap_manifest = {
        "kind": "ConfigMap",
        "apiVersion": "v1",
        "metadata": {
            "name": f"{name}-values",
            "namespace": namespace
        },
        "data": {}
    }
    api.create_namespaced_config_map(namespace, body=configmap_manifest)

    server_deployment_manifest = {
        "kind": "Deployment",
        "apiVersion": "apps/v1",
        "metadata": {
            "name": f"{name}-deployment",
            "namespace": namespace,
            "labels": {
                "app": f"{name}-deployment"
            }
        },
        "spec": {
            "replicas": 1,
            "selector": {
                "matchLabels": {
                    "app": f"{name}-deployment"
                }
            },
            "template": {
                "metadata": {},
                "labels": {
                    "app": f"{name}-deployment"
                },
                "spec": {
                    "containers": [{
                        "name": f"{name}",
                        "image": spec["image"],
                        "imagePullPolicy": spec["imagePullPolicy"],
                        "ports": [{
                            "name": "http",
                            "containerPort": spec["containerPort"],
                            "protocol": "TCP",
                        }],
                        "volumeMounts": [{
                            "name": "config",
                            "mountPath": spec["configMountPath"],
                            "subPath": spec["configSubPath"]
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


def _get_config_map(config_name, namespace) -> tuple[kubernetes.client.V1ConfigMap, kubernetes.client.CoreV1Api]:
    # TODO: add error handling
    client = kubernetes.client.api_client.ApiClient(configuration=kubernetes.config.load_kube_config())
    api = kubernetes.client.CoreV1Api(api_client=client)
    config_map = api.read_namespaced_config_map(name=f"{config_name}-values", namespace=namespace)
    return config_map, api


@kopf.on.create('keyvaluepair')
@kopf.on.update('keyvaluepair')
def create_config_fn(meta, spec, **kwargs):
    config_name = meta["config"]
    namespace = meta["namespace"]
    config_map, api = _get_config_map(config_name, namespace)

    # TODO: maybe assert that spec["value"] is valid yaml which can be parsed in server
    config_map.data[spec["key"]] = spec["value"]  # TODO: in-place update?
    api.patch_namespaced_config_map(name=f"{config_name}-values", namespace=namespace, body=config_map)


@kopf.on.delete('keyvaluepair')
def detete_config_fn(meta, spec, **kwargs):
    config_name = meta["config"]
    namespace = meta["namespace"]
    config_map, api = _get_config_map(config_name, namespace)

    config_map.data.pop(spec["key"])  # TODO: in-place update?
    api.patch_namespaced_config_map(name=f"{config_name}-values", namespace=namespace, body=config_map)
