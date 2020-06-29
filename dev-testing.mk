##the following section is for developers requiring the testing pod to be instantiated with a volume mappig to skampi
location:= $(shell pwd)
kube_path ?= $(shell echo ~/.kube)
k8_path ?= $(shell echo ~/.minikube)
PYTHONPATH=/home/tango/skampi/:/home/tango/skampi/post-deployment/:
testing-pod?=testing-pod
#the port mapping to host
hostPort ?= 2020
testing-config := '{ "apiVersion": "v1","spec":{\
					"containers":[{\
						"image":"$(IMAGE_TO_TEST)",\
						"name":"testing-container",\
						"volumeMounts":[{\
							"mountPath":"/home/tango/skampi/",\
							"name":"testing-volume"}],\
						"env":[{\
          			 		"name": "TANGO_HOST",\
            				"value": "databaseds-tango-base-$(HELM_RELEASE):10000"},{\
							"name": "KUBE_NAMESPACE",\
          					"value": "$(KUBE_NAMESPACE)"},{\
        					"name": "HELM_RELEASE",\
          					"value": "$(HELM_RELEASE)"},{\
							"name": "PYTHONPATH",\
							"value": "$(PYTHONPATH)"}],\
						"ports":[{\
							"containerPort":22,\
							"hostPort":$(hostPort)}],\
						"resources": { \
							"limits": { \
								"cpu": "300m", \
								"memory": "500Mi" },\
							"requests": { \
								"cpu": "200m", \
								"memory": "256Mi" }}}],\
					"nodeSelector": {\
            			"node-role.kubernetes.io/master": ""},\
					"tolerations": [{\
                		"effect": "NoSchedule",\
                		"key": "node-role.kubernetes.io/master",\
                		"operator": "Exists"}],\
					"volumes":[{\
						"name":"testing-volume",\
						"hostPath":{\
							"path":"$(location)",\
							"type":"Directory"}}]}}'

GIT_EMAIL?=user.email.com
GIT_USER?=\"user name\"

##Uncommented make targets are consumed by larger targets and do not need to be displayed when running make -h
tp_run:
	@echo "Starting up testing pod"
	@echo "#######################"; 
	kubectl run $(testing-pod) \
		--image=$(IMAGE_TO_TEST) \
		--namespace $(KUBE_NAMESPACE) \
		--wait \
		--generator=run-pod/v1 \
		--overrides=$(testing-config)

tp_wait:
	@echo "Wating for pod to be ready:"
	kubectl wait --for=condition=Ready pod/$(testing-pod) --namespace $(KUBE_NAMESPACE)
	
tp_run_wait: tp_run tp_wait
	@echo "################################"; 
	@echo "Testing pod started successfully"

tp_pip:
	@echo "Installing Python packages";
	@echo "##########################";
	kubectl exec -it $(testing-pod) --namespace $(KUBE_NAMESPACE) -- bash -c "/usr/bin/python3 -m pip install -r /home/tango/skampi/post-deployment/test_requirements.txt"

tp_cp_kube:
	sudo kubectl cp $(kube_path) $(KUBE_NAMESPACE)/$(testing-pod):/home/tango/.kube/  --namespace $(KUBE_NAMESPACE)

tp_cp_minikube:
	kubectl cp $(k8_path) $(KUBE_NAMESPACE)/$(testing-pod):/home/tango/.minikube/ --namespace $(KUBE_NAMESPACE)

tp_cp: tp_cp_kube tp_cp_minikube

tp_config:
	@echo "Configuring testing pod"
	@echo "#######################";
	@kubectl exec -it --namespace $(KUBE_NAMESPACE) $(testing-pod) -- bash -c " \
		kubectl config --kubeconfig=/home/tango/.kube/config set-credentials minikube --client-key=/home/tango/.minikube/client.key && \
		kubectl config --kubeconfig=/home/tango/.kube/config set-credentials minikube --client-certificate=/home/tango/.minikube/client.crt && \
		kubectl config --kubeconfig=/home/tango/.kube/config set-cluster minikube --certificate-authority=/home/tango/.minikube/ca.crt && \
		echo 'source <(kubectl completion bash)' >>/home/tango/.bashrc && \
		echo 'export HELM_RELEASE=$(HELM_RELEASE)' >> /home/tango/.bashrc && \
		echo 'export KUBE_NAMESPACE=$(KUBE_NAMESPACE)' >> /home/tango/.bashrc && \
		echo 'export GIT_EMAIL=$(GIT_EMAIL)' >> /home/tango/.bashrc && \
		echo 'export GIT_USER=$(GIT_USER)' >> /home/tango/.bashrc && \
		echo 'export VALUES=pipeline.yaml' >> /home/tango/.bashrc && \
		echo 'export TANGO_HOST=databaseds-tango-base-test:10000' >> /home/tango/.bashrc "

deploy_testing_pod: tp_run_wait tp_pip tp_cp tp_config## deploy a testing pod for doing developement inside a k8 pod (this is the same pod used for running CI tests)

sshPort=30022 
httpPort=30080

RELEASE_NAME=dev-testing

install_testing_pod:
	@helm install $(RELEASE_NAME) post-deployment/exploration/dev_testing\
		--set imageToTest=$(IMAGE_TO_TEST) \
		--set kubeNamespace=$(KUBE_NAMESPACE) \
		--set helmRelease=$(HELM_RELEASE) \
		--set pythonPath=$(PYTHONPATH) \
		--set sshPort=$(sshPort) \
		--set hostPath=$(location) \
		--wait --timeout=1m0s
	@kubectl get all -l releaseName=$(RELEASE_NAME)

testing-pod = $(shell echo $$(kubectl get pod -l releaseName='dev-testing' -o=jsonpath='{..metadata.name}') )

set_up_dev_testing: install_testing_pod tp_config test_as_ssh_client
	

describe_dev_testing:
	@chart_name=$$(helm list --filter dev-testing -o=yaml | grep chart | awk '{print $$NF}') && \
		kubectl get all -l chart=$$chart_name


uninstall_testing_pod:
	helm delete $(RELEASE_NAME)

delete_testing_pod: # delete testing pod
	@kubectl delete pod $(testing-pod) --namespace $(KUBE_NAMESPACE)

attach_testing_pod: # open a shell inside the testing pod
	@kubectl exec -it $(testing-pod) --namespace $(KUBE_NAMESPACE) /bin/bash


clean_skampi: # remove any cache or build files on repo created during testing and build jobs
	 git ls-files . --ignored --exclude-standard --others --directory | xargs rm -R -f

ssh_config = "Host kube-host\n\tHostName $(THIS_HOST) \n \tUser ubuntu"

test_as_ssh_client: # set up the  testing pod so that one can ssh back into the host as well as allow other clients to connect using key-pair
	kubectl exec -it $(testing-pod) --namespace $(KUBE_NAMESPACE) -- bash -c "mkdir /home/tango/.ssh/ && ssh-keygen -t rsa -f /home/tango/.ssh/id_rsa -q -P ''"; \
	kubectl exec -it $(testing-pod) --namespace $(KUBE_NAMESPACE) -- bash -c "cat /home/tango/.ssh/id_rsa.pub" >>~/.ssh/authorized_keys; \
	kubectl exec -it $(testing-pod) --namespace $(KUBE_NAMESPACE) -- bash -c "chown tango:tango -R /home/tango/.ssh/"; \
	echo $(ssh_config) >temp; \
	kubectl cp temp $(KUBE_NAMESPACE)/$(testing-pod):/home/tango/.ssh/config --namespace $(KUBE_NAMESPACE); \
	rm temp


check_log_consumer_running: 
	ps aux | awk 
