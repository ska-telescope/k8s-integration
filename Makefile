THIS_HOST := $(shell (ip a 2> /dev/null || ifconfig) | sed -En 's/127.0.0.1//;s/.*inet (addr:)?(([0-9]*\.){3}[0-9]*).*/\2/p' | head -n1)##find IP addresses of this machine, setting THIS_HOST to the first address found
DISPLAY := $(THIS_HOST):0##for GUI applications
XAUTHORITYx ?= ${XAUTHORITY}##for GUI applications
VALUES ?= values.yaml# root level values files. This will override the chart values files.
SKIP_HELM_DEPENDENCY_UPDATE ?= 0# don't run "helm dependency update" on upgrade-chart

INGRESS_HOST ?= k8s.stfc.skao.int## default ingress host
KUBE_NAMESPACE ?= integration#namespace to be used
KUBE_NAMESPACE_SDP ?= integration-sdp#namespace to be used
DOMAIN_TAG ?= test## always set for TANGO_DATABASE_DS
TANGO_DATABASE_DS ?= databaseds-tango-base-$(DOMAIN_TAG)## Stable name for the Tango DB
USE_NGINX ?= true##Traefik or Nginx
HELM_RELEASE ?= test## release name of the chart
DEPLOYMENT_CONFIGURATION ?= skamid## umbrella chart to work with
HELM_HOST ?= $(CAR_HELM_REPOSITORY_URL)## helm host url https
MINIKUBE ?= true## Minikube or not
UMBRELLA_CHART_PATH ?= ./charts/$(DEPLOYMENT_CONFIGURATION)/##Path of the umbrella chart to install

# PSI Low Environment need PROXY values to be set
# This code detects environment and sets the variables
ENV_CHECK := $(shell echo $(CI_ENVIRONMENT_SLUG) | egrep psi-low)
ifneq ($(ENV_CHECK),)
PSI_LOW_PROXY=http://delphoenix.atnf.csiro.au:8888
PSI_LOW_NO_PROXY=localhost,landingpage,oet-rest-$(HELM_RELEASE),127.0.0.1,10.96.0.0/12,192.168.0.0/16,202.9.15.0/24,172.17.0.1/16,.svc.cluster.local
PSI_LOW_PROXY_VALUES = --env=HTTP_PROXY=${PSI_LOW_PROXY} \
				--env=HTTPS_PROXY=${PSI_LOW_PROXY} \
				--env=NO_PROXY=${PSI_LOW_NO_PROXY} \
				--env=http_proxy=${PSI_LOW_PROXY} \
				--env=https_proxy=${PSI_LOW_PROXY} \
				--env=no_proxy=${PSI_LOW_NO_PROXY}

PSI_LOW_SDP_PROXY_VARS= --set sdp.proxy.server=${PSI_LOW_PROXY} \
					--set ska-archiver.enabled=false \
					--set "sdp.proxy.noproxy={${PSI_LOW_NO_PROXY}}"
endif

CI_PROJECT_PATH_SLUG?=skampi##$CI_PROJECT_PATH in lowercase with characters that are not a-z or 0-9 replaced with -. Use in URLs and domain names.
CI_ENVIRONMENT_SLUG?=skampi##The simplified version of the environment name, suitable for inclusion in DNS, URLs, Kubernetes labels, and so on. Available if environment:name is set.
$(shell printf 'global:\n  annotations:\n    app.gitlab.com/app: $(CI_PROJECT_PATH_SLUG)\n    app.gitlab.com/env: $(CI_ENVIRONMENT_SLUG)' > gitlab_values.yaml)

CHART_PARAMS = --set tango-base.xauthority="$(XAUTHORITYx)" \
	--set oet-scripts.ingress.nginx=$(USE_NGINX) \
	--set skuid.ingress.nginx=$(USE_NGINX) \
	--set tango-base.ingress.nginx=$(USE_NGINX) \
	--set webjive.ingress.nginx=$(USE_NGINX) \
	--set global.minikube=$(MINIKUBE) \
	--set sdp.helmdeploy.namespace=$(KUBE_NAMESPACE_SDP) \
	--set global.tango_host=$(TANGO_DATABASE_DS):10000 \
	--set ska-archiver.hostname=$(ARCHIVER_HOST_NAME) \
	--set ska-archiver.dbname=$(ARCHIVER_DBNAME) \
	--set ska-archiver.port=$(ARCHIVER_PORT) \
	--set ska-archiver.dbuser=$(ARCHIVER_DB_USER) \
	--set ska-archiver.dbpassword=$(ARCHIVER_DB_PWD) \
	--values gitlab_values.yaml \
	$(PSI_LOW_SDP_PROXY_VARS)

.DEFAULT_GOAL := help

.PHONY: help

# include makefile targets for release management
-include .make/release.mk

# include makefile targets for testing
-include .make/test.mk

# include makefile targets that EDA deployment
-include .make/archiver.mk

-include PrivateRules.mak

vars: ## Display variables
	@echo "Namespace: $(KUBE_NAMESPACE)"
	@echo "HELM_RELEASE: $(HELM_RELEASE)"
	@echo "VALUES: $(VALUES)"
	@echo "TANGO_DATABASE_DS: $(TANGO_DATABASE_DS)"

k8s: ## Which kubernetes are we connected to
	@echo "Kubernetes cluster-info:"
	@kubectl cluster-info
	@echo ""
	@echo "kubectl version:"
	@kubectl version
	@echo ""
	@echo "Helm version:"
	@$(helm_tiller_prefix) helm version

logs: ## POD logs for descriptor
	@for i in `kubectl -n $(KUBE_NAMESPACE) get pods -l group=example -o=name`; \
	do echo "-------------------"; \
	echo "Logs for $$i"; \
	kubectl -n $(KUBE_NAMESPACE) logs $$i; \
	done


clean: ## clean out references to chart tgz's
	@rm -f ./charts/*/charts/*.tgz ./charts/*/Chart.lock ./charts/*/requirements.lock

namespace: ## create the kubernetes namespace
	@kubectl describe namespace $(KUBE_NAMESPACE) > /dev/null 2>&1 ; \
		K_DESC=$$? ; \
		if [ $$K_DESC -eq 0 ] ; \
		then kubectl describe namespace $(KUBE_NAMESPACE); \
		else kubectl create namespace $(KUBE_NAMESPACE); \
		fi

namespace_sdp: ## create the kubernetes namespace for SDP dynamic deployments
	@kubectl describe namespace $(KUBE_NAMESPACE_SDP) > /dev/null 2>&1 ; \
	K_DESC=$$? ; \
	if [ $$K_DESC -eq 0 ] ; \
	then kubectl describe namespace $(KUBE_NAMESPACE_SDP) ; \
	else kubectl create namespace $(KUBE_NAMESPACE_SDP); \
	fi

delete_namespace: ## delete the kubernetes namespace
	@if [ "default" = "$(KUBE_NAMESPACE)" ] || [ "kube-system" = "$(KUBE_NAMESPACE)" ] ; then \
	echo "You cannot delete Namespace: $(KUBE_NAMESPACE)"; \
	exit 1; \
	else \
	kubectl describe namespace $(KUBE_NAMESPACE) && kubectl delete namespace $(KUBE_NAMESPACE); \
	fi

delete_sdp_namespace: ## delete the kubernetes SDP namespace
	@if [ "default" = "$(KUBE_NAMESPACE_SDP)" ] || [ "kube-system" = "$(KUBE_NAMESPACE_SDP)" ] ; then \
	echo "You cannot delete Namespace: $(KUBE_NAMESPACE_SDP)"; \
	exit 1; \
	else \
	kubectl describe namespace $(KUBE_NAMESPACE_SDP) && kubectl delete namespace $(KUBE_NAMESPACE_SDP); \
	fi

lint_all:  lint## lint ALL of the helm chart

lint:  ## lint the HELM_CHART of the helm chart
	cd $(UMBRELLA_CHART_PATH); pwd; helm lint;

help:  ## show this help.
	@echo "make targets:"
	@grep -E '^[0-9a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ": .*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
	@echo ""; echo "make vars (+defaults):"
	@grep -E '^[0-9a-zA-Z_-]+ \?=.*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = " \\?\\= "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

install: clean namespace namespace_sdp check-archiver-dbname upgrade-chart## install the helm chart on the namespace KUBE_NAMESPACE

uninstall: ## uninstall the helm chart on the namespace KUBE_NAMESPACE
	K_DESC=$$? ; \
	if [ $$K_DESC -eq 0 ] ; \
	then helm uninstall $(HELM_RELEASE) --namespace $(KUBE_NAMESPACE) || true; \
	fi

reinstall-chart: uninstall install ## reinstall the  helm chart on the namespace KUBE_NAMESPACE

upgrade-chart: ## upgrade the helm chart on the namespace KUBE_NAMESPACE
	@if [ "" == "$(HELM_REPO_NAME)" ]; then \
		echo "Installing Helm charts from current ref of git repository..."; \
		test "$(SKIP_HELM_DEPENDENCY_UPDATE)" == "1" || helm dependency update $(UMBRELLA_CHART_PATH); \
	else \
		echo "Deploying from artefact repository..."; \
		helm repo add $(HELM_REPO_NAME) $(HELM_HOST); \
		helm search repo $(HELM_REPO_NAME) | grep DESCRIPTION; \
		helm search repo $(HELM_REPO_NAME) | grep $(UMBRELLA_CHART_PATH); \
	fi
	helm upgrade $(HELM_RELEASE) --install --wait \
		$(CHART_PARAMS) \
		--values $(VALUES) \
		$(UMBRELLA_CHART_PATH) --namespace $(KUBE_NAMESPACE);

template-chart: clean ## template the helm chart on the namespace KUBE_NAMESPACE
	helm dependency update $(UMBRELLA_CHART_PATH); \
	helm template $(HELM_RELEASE) \
        $(CHART_PARAMS) \
		--values $(VALUES) \
		$(UMBRELLA_CHART_PATH) --namespace $(KUBE_NAMESPACE);

install-or-upgrade: upgrade-chart## install or upgrade the release

quotas: namespace## delete and create the kubernetes namespace with quotas
	kubectl -n $(KUBE_NAMESPACE) apply -f resources/namespace_with_quotas.yaml

poddescribe: ## describe Pods executed from Helm chart
	@for i in `kubectl -n $(KUBE_NAMESPACE) get pods -l release=$(HELM_RELEASE) -o=name`; \
	do echo "---------------------------------------------------"; \
	echo "Describe for $${i}"; \
	echo kubectl -n $(KUBE_NAMESPACE) describe $${i}; \
	echo "---------------------------------------------------"; \
	kubectl -n $(KUBE_NAMESPACE) describe $${i}; \
	echo "---------------------------------------------------"; \
	echo ""; echo ""; echo ""; \
	done

podlogs: ## show Helm chart POD logs
	@for i in `kubectl -n $(KUBE_NAMESPACE) get pods -l release=$(HELM_RELEASE) -o=name`; \
	do \
	echo "---------------------------------------------------"; \
	echo "Logs for $${i}"; \
	echo kubectl -n $(KUBE_NAMESPACE) logs $${i}; \
	echo kubectl -n $(KUBE_NAMESPACE) get $${i} -o jsonpath="{.spec.initContainers[*].name}"; \
	echo "---------------------------------------------------"; \
	for j in `kubectl -n $(KUBE_NAMESPACE) get $${i} -o jsonpath="{.spec.initContainers[*].name}"`; do \
	RES=`kubectl -n $(KUBE_NAMESPACE) logs $${i} -c $${j} 2>/dev/null`; \
	echo "initContainer: $${j}"; echo "$${RES}"; \
	echo "---------------------------------------------------";\
	done; \
	echo "Main Pod logs for $${i}"; \
	echo "---------------------------------------------------"; \
	for j in `kubectl -n $(KUBE_NAMESPACE) get $${i} -o jsonpath="{.spec.containers[*].name}"`; do \
	RES=`kubectl -n $(KUBE_NAMESPACE) logs $${i} -c $${j} 2>/dev/null`; \
	echo "Container: $${j}"; echo "$${RES}"; \
	echo "---------------------------------------------------";\
	done; \
	echo "---------------------------------------------------"; \
	echo ""; echo ""; echo ""; \
	done

get_pods: ##lists the pods deployed for a particular namespace. @param: KUBE_NAMESPACE
	kubectl get pods -n $(KUBE_NAMESPACE)

get_versions: ## lists the container images used for particular pods
	kubectl get pods -l release=$(HELM_RELEASE) -n $(KUBE_NAMESPACE) -o jsonpath="{range .items[*]}{.metadata.name}{'\n'}{range .spec.containers[*]}{.name}{'\t'}{.image}{'\n\n'}{end}{'\n'}{end}{'\n'}"
