import json
import os

import kubernetes
from kubernetes import watch
from kubernetes.client import ApiClient, CustomObjectsApi, CoreV1Api, V1ConfigMap, V1Volume, V1Pod
from kopf.testing import KopfRunner

from . import random_namespace, operator_file
from .test_config_server import create_config_server
from .test_crd import create_crd

test_value = {"key": "value", "key2": {"key3": "value3"}}


def create_key_value_pair(client: ApiClient, namespace: str):
    custom_objects_api = CustomObjectsApi(client)
    body = {
        "apiVersion": "datalab.tuwien.ac.at/v1",
        "kind": "KeyValuePair",
        "metadata": {
            "name": "test-config-value-1",
            "namespace": namespace
        },
        "spec": {
            "config": "test-config-server",
            "key": "test",
            "value": test_value
        }

    }
    custom_objects_api.create_namespaced_custom_object("datalab.tuwien.ac.at", "v1", namespace, "keyvaluepairs", body)


def test_key_value_custom_resource_before_server(random_namespace, operator_file):
    client = ApiClient(configuration=kubernetes.config.load_kube_config())
    core_api = CoreV1Api(client)
    custom_objects_api = CustomObjectsApi(client)

    create_crd(client)

    with KopfRunner(['run', '-A', '--verbose', operator_file]) as runner:
        create_key_value_pair(client, random_namespace)

        key_value_watch = watch.Watch()
        entered = False
        for event in key_value_watch.stream(custom_objects_api.list_namespaced_custom_object, "datalab.tuwien.ac.at", "v1", random_namespace, "keyvaluepairs"):
            assert event['type'] == "ADDED"
            obj = event['object']  # object is one of type return_type

            entered = True
            assert obj["metadata"]["name"] == "test-config-value-1"
            key_value_watch.stop()
        assert entered

        create_config_server(client, random_namespace)

        config_server_watch = watch.Watch()
        entered = False
        for event in config_server_watch.stream(custom_objects_api.list_namespaced_custom_object, "datalab.tuwien.ac.at", "v1", random_namespace, "configservers"):
            assert event['type'] == "ADDED"
            obj = event['object']  # object is one of type return_type

            entered = True
            assert obj["metadata"]["name"] == "test-config-server"
            config_server_watch.stop()
        assert entered

        config_map_watch = watch.Watch()
        entered = False
        for event in config_map_watch.stream(core_api.list_namespaced_config_map, random_namespace, timeout_seconds=10):
            assert event['type'] == "ADDED"

            obj = event['object']  # object is one of type return_type
            assert isinstance(obj, V1ConfigMap)

            config_map: V1ConfigMap = obj
            if config_map.metadata.name != "test-config-server-values":
                continue

            entered = True
            assert config_map.data is not None
            assert "test" in config_map.data
            config_test_data = config_map.data["test"]
            assert json.loads(config_test_data) == test_value

            config_map_watch.stop()
        assert entered

    assert runner.exit_code == 0
    assert runner.exception is None


def test_key_value_custom_resource_after_server(random_namespace, operator_file):
    client = ApiClient(configuration=kubernetes.config.load_kube_config())
    core_api = CoreV1Api(client)
    custom_objects_api = CustomObjectsApi(client)

    create_crd(client)

    with KopfRunner(['run', '-A', '--verbose', operator_file]) as runner:
        # config-server
        create_config_server(client, random_namespace)

        config_server_watch = watch.Watch()
        entered = False
        for event in config_server_watch.stream(custom_objects_api.list_namespaced_custom_object, "datalab.tuwien.ac.at", "v1", random_namespace, "configservers"):
            assert event['type'] == "ADDED"
            obj = event['object']  # object is one of type return_type

            entered = True
            assert obj["metadata"]["name"] == "test-config-server"
            config_server_watch.stop()
        assert entered

        # key-value
        create_key_value_pair(client, random_namespace)

        key_value_watch = watch.Watch()
        entered = False
        for event in key_value_watch.stream(custom_objects_api.list_namespaced_custom_object, "datalab.tuwien.ac.at", "v1", random_namespace, "keyvaluepairs"):
            assert event['type'] == "ADDED"
            obj = event['object']  # object is one of type return_type

            entered = True
            assert obj["metadata"]["name"] == "test-config-value-1"
            key_value_watch.stop()
        assert entered

        # config map
        config_map_watch = watch.Watch()
        entered = False
        for event in config_map_watch.stream(core_api.list_namespaced_config_map, random_namespace, timeout_seconds=10):
            assert event['type'] == "ADDED"

            obj = event['object']  # object is one of type return_type
            assert isinstance(obj, V1ConfigMap)

            config_map: V1ConfigMap = obj
            if config_map.metadata.name != "test-config-server-values":
                continue

            entered = True
            assert config_map.data is not None
            assert "test" in config_map.data
            config_test_data = config_map.data["test"]
            assert json.loads(config_test_data) == test_value

            config_map_watch.stop()
        assert entered

    assert runner.exit_code == 0
    assert runner.exception is None

