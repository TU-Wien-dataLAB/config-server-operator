import kubernetes
from kopf.testing import KopfRunner
from kubernetes import watch
from kubernetes.client import ApiClient, CustomObjectsApi, CoreV1Api, V1ConfigMap, V1Volume, V1Pod

from . import random_namespace, operator_file
from .test_crd import create_crd


def create_config_server(client: ApiClient, namespace: str):
    custom_objects_api = CustomObjectsApi(client)
    body = {
        "apiVersion": "datalab.tuwien.ac.at/v1",
        "kind": "ConfigServer",
        "metadata": {
            "name": "test-config-server",
            "namespace": namespace
        },
        "spec": {
            "image": "ghcr.io/tu-wien-datalab/config-server:main",
            "imagePullPolicy": "IfNotPresent",
            "containerPort": 80,
            "configMountPath": "/var/lib/config-server"
        }

    }
    custom_objects_api.create_namespaced_custom_object("datalab.tuwien.ac.at", "v1", namespace, "configservers", body)


def test_config_server_custom_resource(random_namespace, operator_file):
    client = ApiClient(configuration=kubernetes.config.load_kube_config())
    core_api = CoreV1Api(client)
    custom_objects_api = CustomObjectsApi(client)

    create_crd(client)

    with KopfRunner(['run', '-n', random_namespace, '--verbose', operator_file]) as runner:
        config_server_watch = watch.Watch()
        pod_watch = watch.Watch()
        config_map_watch = watch.Watch()
        config_server_stream = config_server_watch.stream(custom_objects_api.list_namespaced_custom_object,
                                                          "datalab.tuwien.ac.at", "v1", random_namespace,
                                                          "configservers", timeout_seconds=30)
        pod_stream = pod_watch.stream(core_api.list_namespaced_pod, random_namespace, timeout_seconds=30)
        config_map_stream = config_map_watch.stream(core_api.list_namespaced_config_map, random_namespace,
                                                    timeout_seconds=30)

        create_config_server(client, random_namespace)

        entered = False
        for event in config_server_stream:
            assert event['type'] == "ADDED"
            obj = event['object']  # object is one of type return_type

            entered = True
            assert obj["metadata"]["name"] == "test-config-server"
            config_server_watch.stop()
        assert entered

        entered = False
        for event in pod_stream:
            assert event['type'] == "ADDED"

            obj = event['object']  # object is one of type return_type
            assert isinstance(obj, V1Pod)

            entered = True

            pod = obj
            assert pod.metadata.name.startswith("test-config-server")
            assert pod.status.phase in ["Running", "Pending"]
            volumes: list[V1Volume] = pod.spec.volumes
            assert any([v.config_map is not None for v in volumes])
            config_volumes = list(filter(lambda v: v.config_map is not None, volumes))
            assert len(config_volumes) == 1
            assert config_volumes[0].name == "config"
            config_map = config_volumes[0].config_map
            assert config_map.name == "test-config-server-values"

            pod_watch.stop()
        assert entered

        entered = False
        for event in config_map_stream:
            assert event['type'] == "ADDED"

            obj = event['object']  # object is one of type return_type
            assert isinstance(obj, V1ConfigMap)

            config_map: V1ConfigMap = obj
            if config_map.metadata.name != "test-config-server-values":
                continue

            entered = True
            assert config_map.data is None

            config_map_watch.stop()
        assert entered

    assert runner.exit_code == 0
    assert runner.exception is None
