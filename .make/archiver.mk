.PHONY: check-archiver-dbname get-service configure-archiver archiver_k8s_test download

CONFIGURE_ARCHIVER = test-configure-archiver # Test runner - run to completion the configuration job in K8s
ARCHIVER_DBNAME ?= default_mvp_archiver_db # Deafult database name used if not provided by user while deploying the archiver
ARCHIVER_CONFIG_FILE ?= $(DEPLOYMENT_CONFIGURATION)/configuration.json## archiver attribute configure json file for MVP-mid to work with

# Checks if the Database name is provided by user while deploying the archiver and notifies the user
check-archiver-dbname:
	@if [ $(ARCHIVER_DBNAME) = default_mvp_archiver_db ]; then \
	echo "Archiver database name is not provided. Setting archiver database name to default value: default_mvp_archiver_db"; \
	fi
	@if [ "$(ARCHIVER_HOST_NAME)" = "" ]; then \
	echo "Archiver host name is not provided."; \
	fi
	@if [ "$(ARCHIVER_PORT)" = "" ]; then \
	echo "Archiver port name is not provided."; \
	fi
	@if [ "$(ARCHIVER_DB_USER)" = "" ]; then \
	echo "Archiver database user is not provided."; \
	fi
	@if [ "$(ARCHIVER_DB_PWD)" = "" ]; then \
	echo "Archiver database password is not provided."; \
	fi

# Get the database service name from MVP deployment
get-service:
	$(eval DBMVPSERVICE := $(shell kubectl get svc -n $(KUBE_NAMESPACE) | grep 10000 |  cut -d " " -f 1)) \
	echo $(DBMVPSERVICE);

# Runs a pod to execute a script. 
# This script configures the archiver for attribute archival defined in json file. Once script is executed, pod is deleted.
configure-archiver:  get-service ##configure attributes to archive
		tar -c resources/archiver/ | \
		kubectl run $(CONFIGURE_ARCHIVER) \
		--namespace $(KUBE_NAMESPACE) -i --wait --restart=Never \
		--image-pull-policy=IfNotPresent \
		--image="artefact.skao.int/ska-tango-images-tango-dsconfig:1.5.1" -- \
		/bin/bash -c "sudo tar xv && \
		sudo curl --retry 4 --retry-delay 1 https://gitlab.com/ska-telescope/ska-archiver/-/raw/master/charts/ska-archiver/data/configure_hdbpp.py -o /resources/archiver/configure_hdbpp.py && \
		cd /resources/archiver && \
		ls -all && \
		sudo python configure_hdbpp.py \
            --f=$(ARCHIVER_CONFIG_FILE) \
            --th=tango://$(TANGO_DATABASE_DS):10000 \
			--ds=$(DBMVPSERVICE) \
			--ns=$(KUBE_NAMESPACE)" && \
		kubectl --namespace $(KUBE_NAMESPACE) delete pod $(CONFIGURE_ARCHIVER);

#
# defines a function to copy the ./test-harness directory into the K8s TEST_RUNNER
# and then runs the requested make target in the container.
# capture the output of the test in a tar file
# stream the tar file base64 encoded to the Pod logs
#
archiver_k8s_test = tar -c post-deployment/ | \
		kubectl run $(TEST_RUNNER) \
		--namespace $(KUBE_NAMESPACE) -i --wait --restart=Never \
		--image-pull-policy=IfNotPresent \
		--image=$(IMAGE_TO_TEST) \
		--limits='cpu=1000m,memory=500Mi' \
		--requests='cpu=900m,memory=400Mi' \
		--env=INGRESS_HOST=$(INGRESS_HOST) \
		$(PSI_LOW_PROXY_VALUES) -- \
		/bin/bash -c "mkdir skampi && tar xv --directory skampi --strip-components 1 --warning=all && cd skampi && \
		make SKUID_URL=skuid-skuid-$(KUBE_NAMESPACE)-$(HELM_RELEASE).$(KUBE_NAMESPACE).svc.cluster.local:9870 KUBE_NAMESPACE=$(KUBE_NAMESPACE) HELM_RELEASE=$(HELM_RELEASE) TANGO_HOST=$(TANGO_HOST) MARK='$(MARK)' FILE='$(FILE)' $1 && \
		tar -czvf /tmp/build.tgz build && \
		echo '~~~~BOUNDARY~~~~' && \
		cat /tmp/build.tgz | base64 && \
		echo '~~~~BOUNDARY~~~~'" \
		2>&1

archiver_k8s_test: smoketest## test the application on K8s
	$(call archiver_k8s_test,test)); \
		status=$$?; \
		rm -fr build; \
		kubectl --namespace $(KUBE_NAMESPACE) logs $(TEST_RUNNER) | \
		perl -ne 'BEGIN {$$on=0;}; if (index($$_, "~~~~BOUNDARY~~~~")!=-1){$$on+=1;next;}; print if $$on % 2;' | \
		base64 -d | tar -xzf -; mkdir -p build; \
		python3 scripts/collect_k8s_logs.py $(KUBE_NAMESPACE) $(KUBE_NAMESPACE_SDP) \
			--pp build/k8s_pretty.txt --dump build/k8s_dump.txt --tests build/k8s_tests.txt; \
		kubectl --namespace $(KUBE_NAMESPACE) delete pod $(TEST_RUNNER); \
		exit $$status
