import logging
import subprocess
from collections import namedtuple

import pytest
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config

from tests.testsupport.helm import HelmTestAdaptor

DEFAULT_USE_TILLER_FLAG = False
DEFAULT_TEST_NAMESPACE = "ci"


def pytest_addoption(parser):
    parser.addoption(
        "--use-tiller-plugin", action="store_true", default=False, help="Wraps helm commands in `helm tiller run --`."
    )
    parser.addoption(
        "--test-namespace", action="store", default=DEFAULT_TEST_NAMESPACE,
        help="The namespace to run infrastructure tests in. Default is 'ci', but should be autogenerated in pipeline based on $CI_JOB_ID"
    )


@pytest.fixture(scope="session")
def test_namespace(pytestconfig):
    test_namespace = pytestconfig.getoption("--test-namespace")
    logging.info("+++ Using test namespace: {}".format(test_namespace))
    return test_namespace


@pytest.fixture(scope="session")
def infratests_context(pytestconfig, test_namespace):
    InfraTestContext = namedtuple('InfraTestContext', ['helm_adaptor'])
    use_tiller_plugin = pytestconfig.getoption("--use-tiller-plugin")
    deployment_tests_are_included = _are_deployment_tests_included(pytestconfig)
    delete_namespace_afterward = False

    if deployment_tests_are_included:
        logging.info("+++ Deployment tests are included.")
        _create_test_namespace_if_needed(test_namespace)
        obj_to_yield = (_build_infrastestcontext_object(InfraTestContext, test_namespace, use_tiller_plugin))
        delete_namespace_afterward = True
    else:
        logging.info("+++ No deployment tests are included.")
        obj_to_yield = InfraTestContext(HelmTestAdaptor(use_tiller_plugin, test_namespace))

    yield obj_to_yield
    if delete_namespace_afterward:
        _delete_namespace(test_namespace)


@pytest.fixture(scope="session")
def helm_adaptor(infratests_context):
    return infratests_context.helm_adaptor


@pytest.fixture(scope="session")
def k8s_api():
    k8s_config.load_kube_config()
    return k8s_client


def _are_deployment_tests_included(pytestconfig):
    markers = pytestconfig.getoption("-m")
    return len(markers) != 0 and "chart_deploy" in markers


def _create_test_namespace_if_needed(test_namespace):
    get_ns_cmd = "kubectl get namespaces {}".format(test_namespace)
    get_ns_result = subprocess.run(get_ns_cmd.split(), stdout=subprocess.PIPE, shell=True)
    if (get_ns_result.returncode != 0):
        create_ns_cmd = "kubectl create namespace {}".format(test_namespace)
        subprocess.run(create_ns_cmd.split(), stdout=subprocess.PIPE, encoding="utf8",
                       check=True)


def _build_infrastestcontext_object(InfraTestContext, test_namespace, use_tiller_plugin):
    helm_adaptor = HelmTestAdaptor(use_tiller_plugin, test_namespace)
    infratestcontext = InfraTestContext(helm_adaptor)
    return infratestcontext


def _delete_namespace(test_namespace):
    delete_ns_cmd = "kubectl delete namespace {}".format(test_namespace)
    subprocess.run(delete_ns_cmd.split(), stdout=subprocess.PIPE, encoding="utf8", check=True)