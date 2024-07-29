import os

import kubernetes
from kubernetes import utils, watch
from kubernetes.client import ApiClient, ApiextensionsV1Api, V1CustomResourceDefinition


def _create_crd(client: ApiClient):
    yaml_file = os.path.join(os.path.dirname(__file__), '../../opr/crd.yaml')
    assert os.path.exists(yaml_file)
    utils.create_from_yaml(client, yaml_file)


def create_crd(client: ApiClient):
    extensions_api = ApiextensionsV1Api(api_client=client)

    config_server_crds = ["configservers.datalab.tuwien.ac.at", "keyvaluepairs.datalab.tuwien.ac.at"]

    crd_watch = watch.Watch()
    crd_stream = crd_watch.stream(extensions_api.list_custom_resource_definition, timeout_seconds=30)

    _create_crd(client)

    created_crds = set()
    for event in crd_stream:
        obj = event['object']
        if obj.metadata.name in config_server_crds:
            created_crds.add(obj.metadata.name)

        if created_crds.issubset(config_server_crds):
            crd_watch.stop()


def test_create_crd():
    client = ApiClient(configuration=kubernetes.config.load_kube_config())
    extensions_api = ApiextensionsV1Api(api_client=client)

    create_crd(client)

    config_server_crds = ["configservers.datalab.tuwien.ac.at", "keyvaluepairs.datalab.tuwien.ac.at"]
    list_crds = lambda namespace: extensions_api.list_custom_resource_definition()
    try:
        crds: list[V1CustomResourceDefinition] = list_crds(None).items
        names = [c.metadata.name for c in crds]
        assert len(names) > 0
        assert set(names).issuperset(config_server_crds)
    finally:
        for name in config_server_crds:
            extensions_api.delete_custom_resource_definition(name=name)
