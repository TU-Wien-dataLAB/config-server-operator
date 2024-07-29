import os
import uuid

import kubernetes
import pytest
from kubernetes.client import ApiClient, CoreV1Api, V1Namespace, V1ObjectMeta, AppsV1Api, CustomObjectsApi, \
    ApiextensionsV1Api


def delete_all(namespace, list_func, delete_func, patch_func):
    resources = list_func(namespace=namespace)
    try:
        resources_list = resources["items"]
    except TypeError:
        resources_list = resources.items
    for resource in resources_list:
        # Operator is not running in fixtures, so we need a force-delete (or this patch).
        patch_body = {
            "metadata": {
                "finalizers": []
            }
        }

        try:
            name = resource.metadata.name
        except AttributeError:
            name = resource["metadata"]["name"]

        try:
            patch_func(name=name, namespace=namespace, body=patch_body)
        except kubernetes.client.exceptions.ApiException as e:
            if e.status == 404:
                pass

        try:
            delete_func(name=name, namespace=namespace)
        except kubernetes.client.exceptions.ApiException as e:
            if e.status == 404:
                pass


def delete_all_custom_objects(crd_api, namespace, plural):
    def list_cr(namespace):
        return crd_api.list_namespaced_custom_object("datalab.tuwien.ac.at", "v1", namespace, plural)

    def delete_cr(name, namespace):
        return crd_api.delete_namespaced_custom_object("datalab.tuwien.ac.at", "v1", namespace, plural, name=name)

    def patch_cr(name, namespace, body):
        return crd_api.patch_namespaced_custom_object("datalab.tuwien.ac.at", "v1", namespace, plural, name=name, body=body)

    delete_all(namespace, list_cr, delete_cr, patch_cr)


@pytest.fixture(scope="function")
def random_namespace():
    client = ApiClient(configuration=kubernetes.config.load_kube_config())
    api = CoreV1Api(api_client=client)

    namespace = f'test-namespace-{uuid.uuid4().hex[:10]}'
    try:
        body = V1Namespace(metadata=V1ObjectMeta(name=namespace))
        api.create_namespace(body=body)
        yield namespace
    finally:
        apps_api = AppsV1Api(api_client=client)
        crd_api = CustomObjectsApi(api_client=client)
        extensions_api = ApiextensionsV1Api(api_client=client)

        delete_all(namespace, api.list_namespaced_pod, api.delete_namespaced_pod, api.patch_namespaced_pod)
        delete_all(namespace, api.list_namespaced_config_map, api.delete_namespaced_config_map, api.patch_namespaced_config_map)
        delete_all(namespace, api.list_namespaced_service, api.delete_namespaced_service, api.patch_namespaced_service)
        delete_all(namespace, apps_api.list_namespaced_deployment, apps_api.delete_namespaced_deployment, apps_api.patch_namespaced_deployment)

        delete_all_custom_objects(crd_api, namespace, "keyvaluepairs")
        delete_all_custom_objects(crd_api, namespace, "configservers")

        config_server_crds = ["configservers.datalab.tuwien.ac.at", "keyvaluepairs.datalab.tuwien.ac.at"]
        for name in config_server_crds:
            extensions_api.delete_custom_resource_definition(name=name)

        api.delete_namespace(name=namespace)
        client.close()


@pytest.fixture(scope="session")
def operator_file():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '../../opr/operator.py'))
